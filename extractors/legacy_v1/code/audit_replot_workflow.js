
export const meta = {
  name: 'audit-replot-vs-source',
  description: 'Audit each chart\'s Phase-4 re-plot against the original image to surface concrete refinement opportunities that the methodology\'s close-the-loop step would catch',
  phases: [
    { title: 'Per-chart audit', detail: '8 agents in parallel, each comparing one chart\'s replot vs original' },
    { title: 'Synthesize', detail: 'roll up findings, answer the methodology question with grounded evidence' },
  ],
}

const CHARTS = ['el-60-a', 'el-60-b', 'el-62', 'el-75', 'el-80', 'el-88', 'el-94', 'el-100']
const BASE = '/Users/csweet1/Documents/projects/CRS_research/figure-recovery-suite'

const AUDIT_SCHEMA = {
  type: 'object',
  required: ['chart_id', 'matches_original_well', 'mismatches_found', 'refinements_suggested', 'evidence_for_iterative_refinement'],
  properties: {
    chart_id: { type: 'string' },
    matches_original_well: { type: 'boolean', description: 'Is the replot visually a faithful reconstruction of the original?' },
    mismatches_found: {
      type: 'array',
      items: {
        type: 'object',
        required: ['kind', 'description', 'severity'],
        properties: {
          kind: { type: 'string', enum: ['missing_series', 'count_mismatch', 'position_error', 'visual_artifact', 'calibration_drift', 'legend_issue', 'other'] },
          description: { type: 'string' },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
        }
      }
    },
    refinements_suggested: {
      type: 'array',
      description: 'Concrete code-level fixes that would address the mismatches',
      items: { type: 'string' }
    },
    evidence_for_iterative_refinement: { type: 'string', description: 'In one sentence: does this chart demonstrate Phase 4 caught (or would catch) something worth fixing?' }
  }
}

phase('Per-chart audit')

const audits = await parallel(
  CHARTS.map(c => () =>
    agent(
      `Audit chart ${c} in the figure-recovery-suite benchmark.\n\n` +
      `Files (use Read to view the images and CSVs):\n` +
      `  Original:        ${BASE}/corpora/aedes-aegypti-2014/charts/${c}/image.png\n` +
      `  Replot:          ${BASE}/extractors/graph-data-extraction/results/aedes-aegypti-2014/${c}/replot.png\n` +
      `  Ground truth:    ${BASE}/corpora/aedes-aegypti-2014/charts/${c}/ground_truth.csv\n` +
      `  Extracted:       ${BASE}/extractors/graph-data-extraction/results/aedes-aegypti-2014/${c}/data.csv\n` +
      `  Run metadata:    ${BASE}/extractors/graph-data-extraction/results/aedes-aegypti-2014/${c}/run3_meta.json\n\n` +
      `Method:\n` +
      `1. Read the original image.\n` +
      `2. Read the replot image.\n` +
      `3. Compare them visually: do the series shapes, ordering, axis ranges, marker counts, and colors match?\n` +
      `4. If anything looks off, document the mismatch (count, position, series, calibration, legend, visual artifact, etc.) with a severity rating.\n` +
      `5. For each mismatch, suggest one concrete code-level refinement that would address it (e.g. "widen the legend exclusion to rows 30-160", "drop the aspect-ratio filter for blue markers near the dashed line", "use a smaller erosion kernel").\n` +
      `6. In one sentence, state whether this chart provides evidence that the Phase-4 close-the-loop step caught (or would catch) something worth fixing.\n\n` +
      `Return structured JSON.`,
      { label: `audit:${c}`, phase: 'Per-chart audit', schema: AUDIT_SCHEMA }
    )
  )
).then(results => results.filter(Boolean))

phase('Synthesize')

const SYNTH_SCHEMA = {
  type: 'object',
  required: ['phase4_is_iterative_in_methodology', 'evidence_summary', 'charts_with_refinement_opportunities', 'overall_assessment', 'concrete_next_actions'],
  properties: {
    phase4_is_iterative_in_methodology: { type: 'boolean' },
    evidence_summary: { type: 'string', description: 'Concise summary of what the per-chart audits found.' },
    charts_with_refinement_opportunities: { type: 'array', items: { type: 'string' } },
    charts_that_look_clean: { type: 'array', items: { type: 'string' } },
    overall_assessment: { type: 'string', description: 'Does this validate that Phase 4 is iterative refinement, or is it currently treated as a one-shot check?' },
    concrete_next_actions: { type: 'array', items: { type: 'string' }, description: 'Specific fixes that should be made to improve the current scores.' }
  }
}

const synthesis = await agent(
  `You have 8 per-chart audit results from the figure-recovery-suite benchmark.\n\n` +
  `Audit findings:\n${JSON.stringify(audits, null, 2)}\n\n` +
  `The user asked: "In the five-phase chart digitization methodology, the workflow re-plots the extracted information. Is the re-plot compared to the original for refinement?"\n\n` +
  `Background:\n` +
  `- Phase 4 of the methodology is "Re-plot and close the loop (REQUIRED)". It says: "Repeat Phase 3 fix → Phase 4 re-plot until the reconstruction matches."\n` +
  `- During the original run on this corpus, Phase 4 caught two bugs that no amount of careful Phase 3 work would have surfaced: (a) §3b mis-applied to a chart without fit curves, (b) a bar-chart replot filter dropping GC1/GC3.\n\n` +
  `Synthesize:\n` +
  `1. Yes/no: is the methodology designed to iterate Phase 4 → Phase 3 → Phase 4 until convergence?\n` +
  `2. Based on these audits, which charts CURRENTLY have refinement opportunities that a Phase-4-driven re-extraction would address?\n` +
  `3. Which charts look clean?\n` +
  `4. Overall: is Phase 4 working as designed (iterative refinement), or has it become a one-shot check in practice?\n` +
  `5. Concrete next actions: what specific code-level fixes would improve the current scores?\n\n` +
  `Return structured JSON.`,
  { label: 'synthesize', phase: 'Synthesize', schema: SYNTH_SCHEMA }
)

return { audits, synthesis }
