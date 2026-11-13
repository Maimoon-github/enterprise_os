import type { ApiClient } from './client'
import { unique } from '../support/ids'

export interface WorkflowGraph {
  nodes: Array<{ id: string; node_type: string; name: string; config: Record<string, unknown> }>
  connections?: Array<{ id: string; source_node_id: string; target_node_id: string; label?: string }>
}

/**
 * Builds a workflow for `agentId` and publishes it, which switches the agent to
 * run it instead of the model. A widget session picks the workflow up when it
 * connects, so embed the widget after this.
 */
export async function publishWorkflow(api: ApiClient, agentId: string, graph: WorkflowGraph): Promise<string> {
  const workflow = await api.post<{ id: string }>('/workflow', { data: { name: unique('E2E flow'), agent_id: agentId } })
  await api.put(`/workflow/${workflow.id}/nodes`, { data: { nodes: graph.nodes, connections: graph.connections ?? [] } })
  await api.put(`/workflow/${workflow.id}`, { data: { status: 'published' } })
  return workflow.id
}
