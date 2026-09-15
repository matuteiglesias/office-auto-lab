import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'
import path from 'node:path'

const siteUrl = process.env.DOCS_SITE_URL
const nav = [
  { text: 'Start Here', link: '/start-here' }, { text: 'Architecture', link: '/architecture/system-overview' },
  { text: 'Office v2', link: '/architecture/coherent-generation-v2' }, { text: 'Components', link: '/components/capture' },
  { text: 'Operations', link: '/operations/local-routines' }, { text: 'Reference', link: '/reference/cli' },
  { text: 'GitHub', link: 'https://github.com/matuteiglesias/office-auto-lab' }
]
const sidebar = [
  { text: 'Start Here', items: [{ text: 'Documentation map', link: '/start-here' }, { text: 'Local development', link: '/getting-started/local-development' }] },
  { text: 'Architecture', collapsed: false, items: [['System overview','system-overview'],['Control state v2','control-state-v2'],['Identity resolution v2','identity-resolution-v2'],['Work-item compiler','work-item-compiler-v1'],['Staff preparation v2','staff-preparation-v2'],['Principal compiler v2','principal-compiler-v2'],['Execution compiler v2','execution-compiler-v2'],['Reentry v2','reentry-v2'],['Coherent generation v2','coherent-generation-v2'],['Run-record health v2','run-record-health-v2'],['Runtime & artifacts','runtime-and-artifact-flow'],['Ownership & state','ownership-and-state'],['Trust boundaries','trust-boundaries']].map(([text,p]) => ({text,link:`/architecture/${p}`})) },
  { text: 'Components', collapsed: false, items: ['capture','evidence','estate-movement'].map(p => ({text:p.replaceAll('-',' '),link:`/components/${p}`})) },
  { text: 'Operations', collapsed: false, items: [['Local routines','local-routines'],['Failure recovery','failure-recovery'],['systemd automation','systemd-automation']].map(([text,p]) => ({text,link:`/operations/${p}`})) },
  { text: 'Reference', collapsed: true, items: ['cli','configuration','artifacts-and-manifests','schemas-and-contracts'].map(p => ({text:p.replaceAll('-',' '),link:`/reference/${p}`})) }
]

export default withMermaid(defineConfig({
  outDir: path.resolve(process.cwd(), 'dist'),
  title: 'Office Auto Lab', description: 'Governed Office v2 compilation and execution preparation', cleanUrls: true,
  lastUpdated: true, sitemap: siteUrl ? { hostname: siteUrl } : undefined, head: [['link',{rel:'icon',href:'/mark.svg'}]],
  // Mirror Vercel's policy in production preview so browser tests exercise the
  // same hydration constraints as deployment.
  vite: { preview: { headers: { 'Content-Security-Policy': "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self'" } } },
  markdown: { theme: { light: 'github-light', dark: 'github-dark' } },
  themeConfig: { logo: '/mark.svg', nav, sidebar, search: { provider: 'local', options: { miniSearch: { searchOptions: { fuzzy: 0.2, prefix: true } } } },
    outline: { level: [2,3], label: 'On this page' }, lastUpdated: { text: 'Source updated' },
    // Function-valued config is deserialized with `new Function`, which the
    // production Content Security Policy correctly blocks.
    editLink: { pattern: 'https://github.com/matuteiglesias/office-auto-lab/edit/main/docs/:path', text: 'Edit canonical source' },
    socialLinks: [{ icon: 'github', link: 'https://github.com/matuteiglesias/office-auto-lab' }], footer: { message: 'Evidence-constrained documentation', copyright: 'Office Auto Lab' }
  }
}))
