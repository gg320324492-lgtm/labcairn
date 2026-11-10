// Supervisor smoke: start a real service, read readiness, stop, check the port.
import net from 'node:net'
import { ServiceSupervisor } from '../src/service-supervisor.mjs'

const workspace = process.argv[2]
const staticDir = process.argv[3] ?? null

const supervisor = new ServiceSupervisor({
  command: 'E:\\LabCairn\\.venv\\Scripts\\labcairn.exe',
  cwd: 'E:\\labcairn-local\\shell-scratch',
  logPath: process.env.LABCAIRN_SHELL_LOG ?? 'E:\\labcairn-local\\shell-logs\\smoke.log',
})

const { starting } = await supervisor.start({ workspace, staticDir })
console.log('service starting:', JSON.stringify(starting))

const health = await fetch(`${starting.origin}/health`).then((r) => r.json())
console.log('health:', JSON.stringify(health))

const exitCode = await supervisor.stop()
console.log('child exit code:', exitCode)

await new Promise((resolve) => setTimeout(resolve, 700))
const stillListening = await new Promise((resolve) => {
  const probe = net.connect({ host: '127.0.0.1', port: starting.port }, () => {
    probe.destroy()
    resolve(true)
  })
  probe.setTimeout(1500, () => {
    probe.destroy()
    resolve(false)
  })
  probe.on('error', () => resolve(false))
})
console.log('port still listening after stop:', stillListening)
console.log('drained log bytes:', supervisor.sink.writtenBytes, 'dropped:', supervisor.sink.droppedBytes)
