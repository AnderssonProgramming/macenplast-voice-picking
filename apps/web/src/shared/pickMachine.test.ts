import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { transition, type PickContext, type PickEvent, type PickState } from './pickMachine'

interface Vector {
  name: string
  state: PickState
  context: PickContext
  event: PickEvent
  expected: {
    state: PickState
    context: PickContext
    effects: unknown[]
  }
}

const vectorsPath = resolve(
  process.cwd(),
  '../../packages/machine-vectors/pick_line_transitions.json',
)
const vectors = JSON.parse(readFileSync(vectorsPath, 'utf-8')) as Vector[]

describe('pickMachine (shared vectors)', () => {
  it.each(vectors)('$name', (vector) => {
    const result = transition(vector.state, vector.context, vector.event)

    expect(result.state).toBe(vector.expected.state)
    expect(result.context).toEqual(vector.expected.context)
    expect(result.effects).toEqual(vector.expected.effects)
  })
})
