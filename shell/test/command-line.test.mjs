/**
 * T08's command-line input policy: every user-supplied argument is refused,
 * never loaded, never guessed at.
 *
 * The channel this watches is the one an installed Windows app gets for
 * free: `process.argv` beyond the executable (a path dragged onto a shortcut,
 * a URL handed to the process), and the `second-instance` event's forwarded
 * `argv`. The plan's baseline (§4.3's second-instance row, §5's "no `file://`
 * and no custom scheme is ever loaded") makes refusal the only correct
 * answer, and a refusal the witness has to be able to see.
 */

import assert from 'node:assert/strict'
import test from 'node:test'

import {
  classifyLaunchArguments,
  classifySecondInstanceArguments,
  refusalLine,
} from '../src/command-line.mjs'

test('a packaged launch keeps only its own executable out of the refusal list', () => {
  const argv = ['C:\\Program Files\\LabCairn\\LabCairn.exe', 'C:\\Users\\pc\\Desktop\\sample.docx']
  const classified = classifyLaunchArguments(argv, { executableCount: 1 })
  assert.deepEqual(classified.refused, ['C:\\Users\\pc\\Desktop\\sample.docx'])
})

test('a dev launch carries two runtime entries before any user argument', () => {
  const argv = ['E:\\LabCairn\\shell\\node_modules\\electron\\dist\\electron.exe', 'E:\\LabCairn\\shell', '--some-flag']
  const classified = classifyLaunchArguments(argv, { executableCount: 2 })
  assert.deepEqual(classified.refused, ['--some-flag'])
})

test('a file:// URL arriving as an argument is refused, not loaded', () => {
  const argv = ['C:\\Program Files\\LabCairn\\LabCairn.exe', 'file:///C:/Windows/win.ini']
  const classified = classifyLaunchArguments(argv, { executableCount: 1 })
  assert.deepEqual(classified.refused, ['file:///C:/Windows/win.ini'])
})

test('a second instance forwards its whole argv and all of it is refused', () => {
  const classified = classifySecondInstanceArguments([
    'E:\\elsewhere\\workspace',
    'labcairn://open-task/00000000-0000-7000-8000-000000000000',
  ])
  assert.equal(classified.refused.length, 2)
  assert.deepEqual(classified.refused, [
    'E:\\elsewhere\\workspace',
    'labcairn://open-task/00000000-0000-7000-8000-000000000000',
  ])
})

test('a second instance that forwards nothing refuses nothing and is not an error', () => {
  const classified = classifySecondInstanceArguments([])
  assert.deepEqual(classified.refused, [])
  assert.deepEqual(classifySecondInstanceArguments(undefined).refused, [])
})

test('every refusal prints as the same line shape the navigation guards use', () => {
  assert.equal(refusalLine('argv', 'file:///C:/x'), 'refused argv file:///C:/x')
  assert.equal(refusalLine('second-instance', '--flag'), 'refused second-instance --flag')
})
