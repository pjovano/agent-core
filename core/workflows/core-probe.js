export const meta = {
  name: 'core-probe',
  description: 'Probe the core: dispatch the core-probe worker once and return its reply, '
    + 'proving that a core workflow and worker load through their symlinks',
  whenToUse: 'only when asked to probe the core',
  phases: [
    { title: 'Probe', detail: 'one core-probe worker' },
  ],
}

const WORKER_TOKEN = 'CORE-PROBE-WORKER-OK'

phase('Probe')
const probe = { agentType: 'core-probe', label: 'core-probe', phase: 'Probe' }
const reply = String(await agent('Probe the core.', probe) ?? '')
return { workflow: 'CORE-PROBE-WORKFLOW-OK', worker_replied: reply.includes(WORKER_TOKEN), reply }
