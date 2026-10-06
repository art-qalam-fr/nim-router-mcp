#!/usr/bin/env node
/**
 * Script d'indexation Qdrant pour Hephaistos-Kit
 * 
 * Collecte les fichiers du projet, génère les embeddings via Ollama
 * et les indexe dans les collections Qdrant appropriées.
 * 
 * Usage:
 *   node .agent/scripts/index-qdrant.mjs [options]
 * 
 * Options:
 *   --provider=nvidia|ollama|openai  Provider d'embeddings (défaut: nvidia)
 *   --model=nvidia/nemotron-3-embed-1b  Modèle d'embedding (défaut: nemotron-3-embed-1b)
 *   --dimensions=2048        Dimensions des vecteurs (défaut: 2048)
 *   --dry-run                  Simuler sans indexer
 *   --force-recreate           Recréer les collections
 *   --verbose                  Mode verbeux
 */

import { readdir, readFile, stat } from 'fs/promises';
import { join, relative, extname, basename, dirname } from 'path';
import { fileURLToPath } from 'url';
import { createHash } from 'crypto';

// Charger manuellement le fichier .env
async function loadEnvFile() {
  try {
    const envPath = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '.env');
    const content = await readFile(envPath, 'utf-8');
    const lines = content.split('\n');
    
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      
      const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
      if (match) {
        const [, key, value] = match;
        // Supprimer les guillemets si présents
        const cleanValue = value.replace(/^["']|["']$/g, '').trim();
        // Forcer l'écrasement avec la valeur du .env (priorité au fichier local)
        process.env[key] = cleanValue;
      }
    }
  } catch (e) {
    // .env non trouvé, ignorer silencieusement
  }
}

await loadEnvFile();

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Configuration par défaut
const CONFIG = {
  // Chemins
  workspaceRoot: join(__dirname, '..', '..'),
  qdrantUrl: process.env.RAG_QDRANT_URL || 'http://localhost:6333',
  
  // Embeddings - Configuration NVIDIA NIM par défaut (2048D)
  provider: process.env.EMBED_PROVIDER || process.env.RAG_QDRANT_PROVIDER || 'nvidia',
  ollamaUrl: process.env.OLLAMA_URL || 'http://localhost:11434',
  nvidiaApiKey: process.env.NVIDIA_API_KEY || process.env.OPENAI_API_KEY,
  nimBaseUrl: process.env.RAG_QDRANT_EMBED_URL || 'https://integrate.api.nvidia.com/v1/embeddings',
  model: process.env.EMBED_MODEL || process.env.RAG_QDRANT_MODEL || 'nvidia/nemotron-3-embed-1b',
  dimensions: parseInt(process.env.RAG_QDRANT_DIMENSIONS || '2048'), // NIM nemotron-3-embed-1b = 2048 dimensions
  
  // Collections
  collections: {
    code: process.env.RAG_QDRANT_COLLECTION_CODE || 'code_index',
    doc: process.env.RAG_QDRANT_COLLECTION_DOC || 'doc_index',
    skill: process.env.RAG_QDRANT_COLLECTION_SKILL || 'skill_index',
    config: process.env.RAG_QDRANT_COLLECTION_CONFIG || 'config_index',
    workflow: process.env.RAG_QDRANT_COLLECTION_WORKFLOW || 'workflow_index',
  },
  
  // Chunking
  chunkSize: parseInt(process.env.RAG_CHUNK_DEFAULT_SIZE || '512'),
  chunkOverlap: parseInt(process.env.RAG_CHUNK_OVERLAP_PERCENT || '15'),
  maxChunkSize: parseInt(process.env.RAG_CHUNK_MAX_SIZE || '1500'),
  
  // Exclusions
  excludePatterns: [
    /\/\.git\//,
    /\/\.venv\//,
    /\/venv\//,
    /\/node_modules\//,
    /\/__pycache__\//,
    /\/\.cursor\//,
    /\/\.devin\//,
    /\/dist\//,
    /\/build\//,
    /\/source-pdf\//,  // Exclusion HTML binaire
    /\.pyc$/,
    /\.pyo$/,
    /\.log$/,
    /\.pid$/,
    /\.tmp$/,
  ],
  
  // Extensions par collection
  extensions: {
    code: ['.js', '.ts', '.tsx', '.jsx', '.py', '.ps1', '.sh', '.css', '.scss', '.html', '.json'],
    doc: ['.md', '.txt', '.markdown', '.rst'],
    config: ['.json', '.yaml', '.yml', '.toml', '.ini', '.config'],
  },
  
  // Répertoires spéciaux pour skills/workflows
  specialDirs: {
    [join('..', '..', '.agent', 'agents')]: 'skill',  // Agents -> skill_index
    [join('..', '..', '.agent', 'skills')]: 'skill',   // Skills -> skill_index
    [join('..', '..', '.agent', 'workflows')]: 'workflow', // Workflows -> workflow_index
    [join('..', '..', '.agent', 'rag')]: 'config',     // RAG config -> config_index
    [join('..', '..', '.agent', 'rules')]: 'config',   // Rules -> config_index
  },
};

// Parse arguments CLI
const args = process.argv.slice(2).reduce((acc, arg) => {
  if (arg === '--dry-run') acc.dryRun = true;
  if (arg === '--force-recreate') acc.forceRecreate = true;
  if (arg === '--verbose') acc.verbose = true;
  if (arg.startsWith('--provider=')) CONFIG.provider = arg.split('=')[1];
  if (arg.startsWith('--model=')) CONFIG.model = arg.split('=')[1];
  if (arg.startsWith('--dimensions=')) CONFIG.dimensions = parseInt(arg.split('=')[1]);
  return acc;
}, { dryRun: false, forceRecreate: false, verbose: false });

// Logger
const log = {
  info: (msg) => console.log(`[INFO] ${msg}`),
  success: (msg) => console.log(`\x1b[32m[OK]\x1b[0m ${msg}`),
  warn: (msg) => console.log(`\x1b[33m[WARN]\x1b[0m ${msg}`),
  error: (msg) => console.log(`\x1b[31m[ERROR]\x1b[0m ${msg}`),
  verbose: (msg) => args.verbose && console.log(`[DEBUG] ${msg}`),
};

// Rate limiter pour l'API d'embeddings (max 2 requêtes/seconde pour éviter le 429)
let lastRequestTime = 0;
const MIN_REQUEST_INTERVAL = 500; // 500ms entre chaque requête

async function rateLimit() {
  const now = Date.now();
  const elapsed = now - lastRequestTime;
  if (elapsed < MIN_REQUEST_INTERVAL) {
    await new Promise(resolve => setTimeout(resolve, MIN_REQUEST_INTERVAL - elapsed));
  }
  lastRequestTime = Date.now();
}

// Retry avec backoff exponentiel
async function fetchWithRetry(url, options, maxRetries = 3) {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      await rateLimit();
      const response = await fetch(url, options);
      
      if (response.status === 429) {
        const delay = Math.pow(2, attempt) * 1000; // 1s, 2s, 4s
        log.warn(`Rate limit atteint (429), retry dans ${delay}ms... (tentative ${attempt + 1}/${maxRetries + 1})`);
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }
      
      return response;
    } catch (e) {
      if (attempt === maxRetries) throw e;
      const delay = Math.pow(2, attempt) * 500;
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  throw new Error(`Max retries (${maxRetries}) exceeded`);
}

/**
 * Génère un embedding via Ollama ou NVIDIA NIM
 */
async function generateEmbedding(text) {
  // Sanitiser le texte pour éviter les caractères UTF-16 invalides
  const sanitized = text
    .replace(/[\uDC00-\uDFFF]/g, '')  // Surrogates orphelins
    .replace(/[\uD800-\uDBFF](?![\uDC00-\uDFFF])/g, '')  // Leading sans trailing
    .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '')  // Caractères de contrôle
    .slice(0, 8000);  // Limite pour éviter les payloads trop grandes

  if (CONFIG.provider === 'ollama') {
    const response = await fetch(`${CONFIG.ollamaUrl}/api/embeddings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: CONFIG.model,
        prompt: sanitized,
      }),
    });
    
    if (!response.ok) {
      throw new Error(`Ollama error: ${response.status} ${await response.text()}`);
    }
    
    const data = await response.json();
    return data.embedding;
  } 
  
  if (CONFIG.provider === 'nvidia' || CONFIG.provider === 'openai') {
    if (!CONFIG.nvidiaApiKey) {
      throw new Error('NVIDIA_API_KEY (ou OPENAI_API_KEY) manquante pour le provider nvidia');
    }

    const response = await fetchWithRetry(CONFIG.nimBaseUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${CONFIG.nvidiaApiKey}`,
      },
      body: JSON.stringify({
        model: CONFIG.model || 'nvidia/nemotron-3-embed-1b',
        input: sanitized,
        input_type: 'passage',
      }),
    });

    if (!response.ok) {
      throw new Error(`NVIDIA NIM error: ${response.status} ${await response.text()}`);
    }

    const data = await response.json();
    return data.data[0].embedding;
  }

  throw new Error(`Provider inconnu: ${CONFIG.provider}`);
}

/**
 * Vérifie si Qdrant est accessible
 */
async function checkQdrant() {
  try {
    const response = await fetch(`${CONFIG.qdrantUrl}/healthz`);
    return response.ok;
  } catch (e) {
    return false;
  }
}

/**
 * Récupère les informations d'une collection
 */
async function getCollectionInfo(name) {
  try {
    const response = await fetch(`${CONFIG.qdrantUrl}/collections/${name}`);
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`Qdrant error: ${response.status}`);
    return await response.json();
  } catch (e) {
    log.error(`Impossible de récupérer info collection ${name}: ${e.message}`);
    return null;
  }
}

/**
 * Crée une collection si elle n'existe pas
 */
async function createCollection(name, recreate = false) {
  const exists = await getCollectionInfo(name);
  
  if (exists && !recreate) {
    log.verbose(`Collection ${name} existe déjà`);
    return true;
  }
  
  if (exists && recreate) {
    log.info(`Suppression collection ${name}...`);
    await fetch(`${CONFIG.qdrantUrl}/collections/${name}`, { method: 'DELETE' });
  }
  
  log.info(`Création collection ${name} (${CONFIG.dimensions}D)...`);
  
  // Détecter si la collection utilise des vecteurs nommés
  const response = await fetch(`${CONFIG.qdrantUrl}/collections/${name}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      vectors: {
        size: CONFIG.dimensions,
        distance: 'Cosine',
      },
    }),
  });
  
  if (!response.ok) {
    const error = await response.text();
    // Essayer avec vecteur nommé "dense" (format alternatif)
    const response2 = await fetch(`${CONFIG.qdrantUrl}/collections/${name}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        vectors: {
          dense: {
            size: CONFIG.dimensions,
            distance: 'Cosine',
          },
        },
      }),
    });
    
    if (!response2.ok) {
      throw new Error(`Création collection échouée: ${error}, puis ${await response2.text()}`);
    }
    
    log.verbose(`Collection ${name} créée avec vecteur nommé 'dense'`);
    return true;
  }
  
  log.success(`Collection ${name} créée`);
  return true;
}

// Cache du format des collections (standard vs dense)
const collectionFormatCache = new Map();

/**
 * Détecte le format de vecteur utilisé par une collection
 */
async function detectCollectionFormat(collection) {
  if (collectionFormatCache.has(collection)) {
    return collectionFormatCache.get(collection);
  }
  
  try {
    const info = await getCollectionInfo(collection);
    if (!info?.result?.config?.params?.vectors) {
      return 'standard'; // Par défaut
    }
    
    const vectors = info.result.config.params.vectors;
    // Si la clé "dense" existe, c'est le format nommé
    const format = vectors.dense ? 'dense' : 'standard';
    collectionFormatCache.set(collection, format);
    log.verbose(`Format détecté pour ${collection}: ${format}`);
    return format;
  } catch (e) {
    return 'standard'; // Fallback
  }
}

/**
 * Ajoute des points à une collection
 */
async function upsertPoints(collection, points) {
  if (points.length === 0) return 0;
  
  const format = await detectCollectionFormat(collection);
  
  // Préparer les points selon le format
  let pointsToUpsert = points;
  if (format === 'dense') {
    pointsToUpsert = points.map(p => ({
      ...p,
      vector: { dense: p.vector },
    }));
  }
  
  const response = await fetch(`${CONFIG.qdrantUrl}/collections/${collection}/points?wait=true`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ points: pointsToUpsert }),
  });
  
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Upsert échoué: ${error}`);
  }
  
  return points.length;
}

/**
 * Détermine si un fichier doit être exclu
 */
function shouldExclude(filePath) {
  return CONFIG.excludePatterns.some(pattern => pattern.test(filePath));
}

/**
 * Détermine la collection cible pour un fichier
 */
function getTargetCollection(filePath, ext) {
  // Vérifier les répertoires spéciaux d'abord
  for (const [dir, collection] of Object.entries(CONFIG.specialDirs)) {
    const absoluteDir = join(__dirname, dir);
    if (filePath.includes(absoluteDir) || filePath.includes(dir.replace(/\//g, '\\'))) {
      return CONFIG.collections[collection] || collection;
    }
  }
  
  // Sinon, déterminer par extension
  if (CONFIG.extensions.code.includes(ext)) return CONFIG.collections.code;
  if (CONFIG.extensions.doc.includes(ext)) return CONFIG.collections.doc;
  if (CONFIG.extensions.config.includes(ext)) return CONFIG.collections.config;
  
  // Défaut: doc_index
  return CONFIG.collections.doc;
}

/**
 * Découpe un texte en chunks avec chevauchement
 */
function chunkText(text, size = CONFIG.chunkSize, overlap = CONFIG.chunkOverlap) {
  const chunks = [];
  const overlapSize = Math.floor(size * (overlap / 100));
  const step = size - overlapSize;
  
  for (let i = 0; i < text.length; i += step) {
    const chunk = text.slice(i, i + size);
    if (chunk.length < 50) continue;  // Ignorer les chunks trop petits
    chunks.push({
      text: chunk,
      start: i,
      end: i + chunk.length,
    });
  }
  
  return chunks;
}

/**
 * Génère un ID unique pour un chunk
 */
function generateId(filePath, index) {
  const hash = createHash('md5').update(`${filePath}:${index}`).digest('hex');
  return hash.slice(0, 32);
}

/**
 * Collecte tous les fichiers à indexer
 */
async function collectFiles(dir, files = []) {
  const entries = await readdir(dir, { withFileTypes: true });
  
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    
    if (shouldExclude(fullPath)) {
      log.verbose(`Exclu: ${fullPath}`);
      continue;
    }
    
    if (entry.isDirectory()) {
      await collectFiles(fullPath, files);
    } else if (entry.isFile()) {
      const ext = extname(entry.name).toLowerCase();
      const allExts = [...CONFIG.extensions.code, ...CONFIG.extensions.doc, ...CONFIG.extensions.config];
      
      if (allExts.includes(ext)) {
        files.push({ path: fullPath, ext, name: entry.name });
      }
    }
  }
  
  return files;
}

/**
 * Indexe un fichier
 */
async function indexFile(fileInfo, stats) {
  const { path: filePath, ext } = fileInfo;
  const relativePath = relative(CONFIG.workspaceRoot, filePath);
  const collection = getTargetCollection(filePath, ext);
  
  log.verbose(`Indexation: ${relativePath} → ${collection}`);
  
  try {
    const content = await readFile(filePath, 'utf-8');
    
    if (!content.trim()) {
      log.verbose(`Fichier vide: ${relativePath}`);
      return;
    }
    
    // Découper en chunks
    const chunks = chunkText(content);
    
    if (args.dryRun) {
      log.info(`[DRY-RUN] ${relativePath}: ${chunks.length} chunks → ${collection}`);
      stats[collection] = (stats[collection] || 0) + chunks.length;
      return;
    }
    
    // Générer les embeddings et préparer les points
    const points = [];
    for (let i = 0; i < chunks.length; i++) {
      const chunk = chunks[i];
      
      try {
        const embedding = await generateEmbedding(chunk.text);
        
        points.push({
          id: generateId(relativePath, i),
          vector: embedding,
          payload: {
            source: relativePath,
            text: chunk.text.slice(0, 1000),  // Limiter la taille du payload
            chunk_index: i,
            total_chunks: chunks.length,
            extension: ext,
            start_char: chunk.start,
            end_char: chunk.end,
            indexed_at: new Date().toISOString(),
          },
        });
        
        // Batch upsert tous les 50 points
        if (points.length >= 50) {
          const count = await upsertPoints(collection, points.splice(0, 50));
          stats[collection] = (stats[collection] || 0) + count;
        }
      } catch (e) {
        log.error(`Erreur embedding chunk ${i} de ${relativePath}: ${e.message}`);
        stats.errors = (stats.errors || 0) + 1;
      }
    }
    
    // Upsert les points restants
    if (points.length > 0) {
      const count = await upsertPoints(collection, points);
      stats[collection] = (stats[collection] || 0) + count;
    }
    
    stats.filesProcessed++;
    
  } catch (e) {
    log.error(`Erreur lecture ${relativePath}: ${e.message}`);
    stats.errors = (stats.errors || 0) + 1;
  }
}

/**
 * Fonction principale
 */
async function main() {
  console.log('\n🚀 Indexation Qdrant - Hephaistos-Kit\n');
  console.log('='.repeat(50));
  
  // Vérifier Qdrant
  log.info('Vérification connexion Qdrant...');
  if (!(await checkQdrant())) {
    log.error(`Qdrant inaccessible à ${CONFIG.qdrantUrl}`);
    log.info('Assurez-vous que Qdrant est démarré: docker run -p 6333:6333 qdrant/qdrant');
    process.exit(1);
  }
  log.success('Qdrant connecté');
  
  // Vérifier Ollama si utilisé
  if (CONFIG.provider === 'ollama') {
    try {
      const response = await fetch(`${CONFIG.ollamaUrl}/api/tags`);
      if (!response.ok) throw new Error('Ollama non disponible');
      log.success(`Ollama connecté (${CONFIG.model})`);
    } catch (e) {
      log.error(`Ollama inaccessible à ${CONFIG.ollamaUrl}`);
      log.info('Assurez-vous qu\'Ollama est démarré et que le modèle est pull:');
      log.info(`  ollama pull ${CONFIG.model}`);
      process.exit(1);
    }
  }
  
  // Créer les collections
  log.info('Préparation des collections...');
  for (const [type, name] of Object.entries(CONFIG.collections)) {
    try {
      await createCollection(name, args.forceRecreate);
    } catch (e) {
      log.error(`Échec création collection ${name}: ${e.message}`);
      process.exit(1);
    }
  }
  
  // Collecter les fichiers
  log.info('Collecte des fichiers...');
  const files = await collectFiles(CONFIG.workspaceRoot);
  log.success(`${files.length} fichiers trouvés`);
  
  if (files.length === 0) {
    log.warn('Aucun fichier à indexer');
    return;
  }
  
  // Statistiques
  const stats = {
    filesProcessed: 0,
    errors: 0,
  };
  
  // Indexer les fichiers
  console.log('\n📦 Indexation en cours...\n');
  const startTime = Date.now();
  
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const progress = `[${i + 1}/${files.length}]`;
    process.stdout.write(`${progress} ${relative(CONFIG.workspaceRoot, file.path)}`.slice(0, 70).padEnd(70) + '\r');
    
    await indexFile(file, stats);
  }
  
  const duration = ((Date.now() - startTime) / 1000).toFixed(1);
  
  // Rapport final
  console.log('\n');
  console.log('='.repeat(50));
  console.log('\n📊 Rapport d\'indexation\n');
  
  console.log(`⏱️  Durée: ${duration}s`);
  console.log(`📁 Fichiers traités: ${stats.filesProcessed}/${files.length}`);
  console.log(`❌ Erreurs: ${stats.errors}`);
  console.log('\n📚 Collections:');
  
  for (const [type, name] of Object.entries(CONFIG.collections)) {
    const count = stats[name] || 0;
    console.log(`   ${name}: ${count} points`);
  }
  
  const total = Object.values(stats).reduce((a, b) => typeof b === 'number' ? a + b : a, 0) - stats.filesProcessed - stats.errors;
  console.log(`\n   Total: ${total} points indexés`);
  
  console.log('\n' + '='.repeat(50));
  log.success('Indexation terminée! 🎉\n');
}

// Gestion des erreurs
process.on('unhandledRejection', (err) => {
  log.error(`Erreur non gérée: ${err.message}`);
  console.error(err);
  process.exit(1);
});

// Exécution
main().catch(err => {
  log.error(`Échec: ${err.message}`);
  console.error(err);
  process.exit(1);
});
