import { cp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const docs = path.resolve(root, '../docs')
const generated = path.join(root, '.generated/site')
const repoUrl = 'https://github.com/matuteiglesias/office-auto-lab/blob/main/'

export const PUBLIC_ROOTS = new Set(['architecture', 'components', 'getting-started', 'operations', 'reference', 'case-studies', 'historical'])
export const PUBLIC_FILES = new Set([
  'README.md', 'documentation-maintenance.md', 'documentation_coverage.md',
  'documentation_inventory.md', 'documentation_canonicality_map.md',
  'capture_processing_layer.md', 'systemd_timers.md'
])
export const EXCLUDED_SEGMENTS = /(^|\/)(documentation_program|context|notes|retrofit|inbox|artifacts?)(\/|$)/i
export function isPublic(rel, text) {
  const clean = rel.replaceAll('\\', '/')
  if (EXCLUDED_SEGMENTS.test(clean) || /(^|\/)\.env($|\.)|\.tfstate($|\.)/i.test(clean)) return false
  if (/^(internal|draft|private|search)\s*:\s*(true|false)/im.test(text)) {
    if (/^(internal|draft|private)\s*:\s*true/im.test(text) || /^search\s*:\s*false/im.test(text)) return false
  }
  return PUBLIC_FILES.has(clean) || PUBLIC_ROOTS.has(clean.split('/')[0])
}

async function walk(dir, base = dir) {
  const files = []
  for (const item of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, item.name)
    if (item.isDirectory()) files.push(...await walk(full, base))
    else files.push(path.relative(base, full))
  }
  return files
}

function rewriteLinks(text, sourceRel) {
  return text.replace(/\]\(([^)#]+)(#[^)]+)?\)/g, (all, target, hash = '') => {
    if (/^(https?:|mailto:|\/)/.test(target)) return all
    const resolved = path.posix.normalize(path.posix.join(path.posix.dirname(sourceRel), target))
    if (target.endsWith('.md') && (PUBLIC_FILES.has(resolved) || PUBLIC_ROOTS.has(resolved.split('/')[0]))) {
      const route = resolved === 'README.md' ? '/start-here' : `/${resolved.replace(/\.md$/, '')}`
      return `](${route}${hash})`
    }
    if (resolved.startsWith('../') || !target.endsWith('.md')) {
      const repoPath = path.posix.normalize(path.posix.join('docs', path.posix.dirname(sourceRel), target)).replace(/^\.\.\//, '')
      return `](${repoUrl}${repoPath}${hash})`
    }
    return all
  })
}

if (!existsSync(docs)) throw new Error(`Canonical documentation is unavailable at ${docs}. Enable Vercel's “Include source files outside of the Root Directory” setting.`)
await rm(generated, { recursive: true, force: true })
await mkdir(generated, { recursive: true })
await cp(path.join(root, 'scaffold'), generated, { recursive: true })

const manifest = []
for (const rel of (await walk(docs)).filter(file => file.endsWith('.md')).sort()) {
  const text = await readFile(path.join(docs, rel), 'utf8')
  if (!isPublic(rel, text)) continue
  const output = rel === 'README.md' ? 'start-here.md' : rel
  await mkdir(path.dirname(path.join(generated, output)), { recursive: true })
  await writeFile(path.join(generated, output), rewriteLinks(text, rel))
  manifest.push({ route: `/${output.replace(/(^|\/)README\.md$/, '$1index').replace(/\.md$/, '')}`, source: `docs/${rel}` })
}
await writeFile(path.join(generated, 'public-routes.json'), `${JSON.stringify(manifest, null, 2)}\n`)
console.log(`Synced ${manifest.length} canonical public pages to ${generated}`)
