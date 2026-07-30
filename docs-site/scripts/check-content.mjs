import { readFile, readdir } from 'node:fs/promises'
import path from 'node:path'
import { spawnSync } from 'node:child_process'

const root = path.resolve(import.meta.dirname, '..')
const sync = spawnSync(process.execPath, ['scripts/sync-content.mjs'], { cwd: root, stdio: 'inherit' })
if (sync.status) process.exit(sync.status)
const site = path.join(root, '.generated/site')
const manifest = JSON.parse(await readFile(path.join(site, 'public-routes.json')))
const failures = []
const routes = new Set(manifest.map(x => x.route))
if (routes.size !== manifest.length) failures.push('duplicate public routes')
for (const item of manifest) {
  if (/(^|\/)(documentation_program|context|notes|retrofit|inbox)(\/|$)|(^|\/)\.env($|\.)|\.tfstate($|\.)/i.test(item.source)) failures.push(`excluded source leaked: ${item.source}`)
}
for (const required of ['/start-here', '/architecture/system-overview', '/components/office-compile', '/operations/local-routines', '/reference/cli', '/case-studies/gcp-project-health-retrofit']) {
  if (!routes.has(required)) failures.push(`required route missing: ${required}`)
}
async function walk(dir) { return (await readdir(dir, { withFileTypes: true })).flatMap(x => x.isDirectory() ? [] : [path.join(dir, x.name)]) }
const scaffold = await Promise.all((await walk(path.join(site))).filter(x => x.endsWith('.md')).map(x => readFile(x, 'utf8')))
if (scaffold.join('\n').match(/(-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|AIza[0-9A-Za-z_-]{30,}|ghp_[0-9A-Za-z]{30,})/)) failures.push('obvious secret pattern found')
const config = await readFile(path.join(site, '.vitepress/config.mts'), 'utf8')
for (const route of ['/start-here', '/architecture/system-overview', '/components/office-compile', '/operations/local-routines', '/reference/cli', '/case-studies/gcp-project-health-retrofit']) {
  if (!config.includes(route)) failures.push(`navigation does not declare ${route}`)
}
if (failures.length) { console.error(failures.join('\n')); process.exit(1) }
console.log(`Content checks passed: ${manifest.length} unique public routes; exclusions, required routes, navigation, and secret patterns verified.`)
