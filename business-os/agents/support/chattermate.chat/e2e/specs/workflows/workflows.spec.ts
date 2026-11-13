import { test, expect, expectUnchanged, publishWorkflow, AI_REPLY, type WorkflowGraph } from '@e2e'

// A published workflow runs instead of the model: scripted steps, no AI calls.

test.describe('workflows', () => {
  test('a one-message workflow greets once on load and answers each message once, without the AI @workflows', async ({ agent, adminApi, widget, llm }) => {
    await publishWorkflow(adminApi, agent.id, {
      nodes: [{ id: 'msg-1', node_type: 'message', name: 'Greeting', config: { message_text: 'Hello from our workflow.' } }],
    })

    await widget.embed()
    await widget.open()
    await expect(widget.agentMessages).toHaveText(['Hello from our workflow.'], AI_REPLY)

    await widget.send('hi')
    await expect(widget.agentMessages).toHaveText(['Hello from our workflow.', 'Hello from our workflow.'], AI_REPLY)
    await expectUnchanged('agent messages', () => widget.agentMessages.allTextContents())
    expect(await llm.requests(agent)).toHaveLength(0)
  })

  test('a workflow asks a question and branches on the answer @workflows', async ({ agent, adminApi, widget }) => {
    await publishWorkflow(adminApi, agent.id, {
      nodes: [
        { id: 'ask', node_type: 'user_input', name: 'Ask Plan', config: { prompt_message: 'Which plan are you on? (pro/basic)', confirmation_message: 'Thanks — {{ask_plan_input}} it is.' } },
        { id: 'is-pro', node_type: 'condition', name: 'Is Pro', config: { condition_expression: '{{ask_plan_input}} === pro' } },
        { id: 'pro', node_type: 'message', name: 'Pro', config: { message_text: 'Pro customers get priority support.' } },
        { id: 'basic', node_type: 'message', name: 'Basic', config: { message_text: 'Basic customers can upgrade any time.' } },
      ],
      connections: [
        { id: 'c1', source_node_id: 'ask', target_node_id: 'is-pro' },
        { id: 'c2', source_node_id: 'is-pro', target_node_id: 'pro', label: 'true' },
        { id: 'c3', source_node_id: 'is-pro', target_node_id: 'basic', label: 'false' },
      ],
    })

    await widget.embed()
    await widget.open()
    await expect(widget.lastAgentMessage()).toHaveText('Which plan are you on? (pro/basic)', AI_REPLY)

    await widget.send('pro')
    await expect(widget.lastAgentMessage()).toHaveText('Pro customers get priority support.', AI_REPLY)
    await expect(widget.agentMessages).toContainText(['Thanks — pro it is.'])
    await expect(widget.agentMessages.filter({ hasText: 'Basic customers' })).toHaveCount(0)
  })

  // Plan AND seats, built the way the dashboard's condition builder saves it.
  function planAndSeats(wired: Array<'true' | 'false'> = ['true', 'false']): WorkflowGraph {
    return {
      nodes: [
        { id: 'ask-plan', node_type: 'user_input', name: 'Ask Plan', config: { prompt_message: 'Which plan are you on?' } },
        { id: 'ask-seats', node_type: 'user_input', name: 'Ask Seats', config: { prompt_message: 'How many seats?' } },
        {
          id: 'big-pro', node_type: 'condition', name: 'Big Pro',
          config: {
            condition_groups: [{
              id: 'g1', logicalOperator: 'AND', rules: [
                { id: 'r1', variable: 'ask_plan_input', operator: '===', value: 'pro' },
                { id: 'r2', variable: 'ask_seats_input', operator: '>', value: '3' },
              ],
            }],
            condition_expression: '({{ask_plan_input}} === "pro" AND {{ask_seats_input}} > 3)',
          },
        },
        { id: 'priority', node_type: 'message', name: 'Priority', config: { message_text: 'You get a dedicated account manager.' } },
        { id: 'standard', node_type: 'message', name: 'Standard', config: { message_text: 'Our team will get back to you.' } },
      ],
      connections: [
        { id: 'c1', source_node_id: 'ask-plan', target_node_id: 'ask-seats' },
        { id: 'c2', source_node_id: 'ask-seats', target_node_id: 'big-pro' },
        ...wired.map((branch) => ({ id: `c-${branch}`, source_node_id: 'big-pro', target_node_id: branch === 'true' ? 'priority' : 'standard', label: branch })),
      ],
    }
  }

  const answers = [
    { plan: 'pro', seats: '5', reply: 'You get a dedicated account manager.', why: 'both rules hold' },
    { plan: 'pro', seats: '2', reply: 'Our team will get back to you.', why: 'one rule fails' },
    { plan: 'basic" OR "a" === "a', seats: '5', reply: 'Our team will get back to you.', why: 'an answer that looks like a condition is just text' },
    { plan: 'pro', seats: 'lots', reply: 'Our team will get back to you.', why: 'a non-number is never "greater than"' },
  ]
  for (const { plan, seats, reply, why } of answers) {
    test(`a combined condition routes on both answers: ${why} @workflows`, async ({ agent, adminApi, widget }) => {
      await publishWorkflow(adminApi, agent.id, planAndSeats())
      await widget.embed()
      await widget.open()
      await expect(widget.lastAgentMessage()).toHaveText('Which plan are you on?', AI_REPLY)
      await widget.send(plan)
      await expect(widget.lastAgentMessage()).toHaveText('How many seats?', AI_REPLY)
      await widget.send(seats)
      await expect(widget.lastAgentMessage()).toHaveText(reply, AI_REPLY)
    })
  }

  test('a condition with no branch for its result stops instead of taking the other one @workflows', async ({ agent, adminApi, widget, llm }) => {
    await publishWorkflow(adminApi, agent.id, planAndSeats(['true']))
    await widget.embed()
    await widget.open()
    await expect(widget.lastAgentMessage()).toHaveText('Which plan are you on?', AI_REPLY)
    await widget.send('basic')
    await expect(widget.lastAgentMessage()).toHaveText('How many seats?', AI_REPLY)
    await widget.send('1')

    await expectUnchanged('agent messages', () => widget.agentMessages.allTextContents())
    await expect(widget.agentMessages.filter({ hasText: 'dedicated account manager' })).toHaveCount(0)
    expect(await llm.requests(agent)).toHaveLength(0)
  })
})
