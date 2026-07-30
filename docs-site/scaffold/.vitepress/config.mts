import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'
import path from 'node:path'

const siteUrl = process.env.DOCS_SITE_URL
const nav = [
  { text: 'Start Here', link: '/start-here' }, { text: 'Architecture', link: '/architecture/system-overview' },
  { text: 'Components', link: '/components/office-compile' }, { text: 'Operations', link: '/operations/local-routines' },
  { text: 'Reference', link: '/reference/cli' }, { text: 'Case Studies', link: '/case-studies/gcp-project-health-retrofit' },
  { text: 'GitHub', link: 'https://github.com/matuteiglesias/office-auto-lab' }
]
const sidebar = [
  { text: 'Start Here', items: [{ text: 'Documentation map', link: '/start-here' }, { text: 'Local development', link: '/getting-started/local-development' }] },
  { text: 'Architecture', collapsed: false, items: [['System overview','system-overview'],['Runtime & artifacts','runtime-and-artifact-flow'],['Ownership & state','ownership-and-state'],['Trust boundaries','trust-boundaries'],['GCP Repo Health','repo-health-gcp']].map(([text,p]) => ({text,link:`/architecture/${p}`})) },
  { text: 'Components', collapsed: false, items: ['office-compile','staff','capture','evidence','repo-health'].map(p => ({text:p.replaceAll('-',' '),link:`/components/${p}`})) },
  { text: 'Operations', collapsed: false, items: [['Local routines','local-routines'],['Failure recovery','failure-recovery'],['systemd automation','systemd-automation'],['Repo Health local','repo-health-local'],['Repo Health GCP','repo-health-gcp'],['GCP cost & teardown','repo-health-gcp-cost-and-teardown']].map(([text,p]) => ({text,link:`/operations/${p}`})) },
  { text: 'Reference', collapsed: true, items: ['cli','configuration','artifacts-and-manifests','schemas-and-contracts','repo-health-plugins','repo-health-gcp-security','repo-health-gcp-data-model'].map(p => ({text:p.replaceAll('-',' '),link:`/reference/${p}`})) },
  { text: 'Case Studies', items: [{ text: 'GCP engineering case', link: '/case-studies/gcp-project-health-retrofit' }] }
]

export default withMermaid(defineConfig({
  outDir: path.resolve(process.cwd(), 'dist'),
  title: 'Office Auto Lab', description: 'Governed operational compilation and repository health', cleanUrls: true,
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
