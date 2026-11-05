/**
 * Fixed per-stage interview evaluation rubric, mirroring
 * backend/recruiting/evaluation_rubric.py's RUBRICS verbatim (same field
 * ids/labels/order/types) so submitted responses validate against the
 * backend's shape.
 */
export const RUBRICS = {
  recruiter_screening: [
    {
      title: "Background Fitness",
      fields: [
        {
          id: "bg_match",
          label: "Does the candidate's background match the role requirements?",
          valueType: "pass_fail",
        },
        {
          id: "bg_consistency",
          label:
            "Are the candidate's resume, LinkedIn, and application answers consistent?",
          valueType: "pass_fail",
        },
        {
          id: "bg_strength",
          label: "Background strength",
          valueType: "score",
          hasNotes: true,
        },
      ],
    },
    {
      title: "Cultural Fitness",
      fields: [
        {
          id: "format_compliance",
          label: "Did the candidate meet the required format instructions?",
          valueType: "pass_fail",
        },
        {
          id: "mission_alignment",
          label:
            "Does the candidate demonstrate alignment with the community's mission?",
          valueType: "pass_fail",
        },
        {
          id: "writing_quality",
          label: "Writing quality",
          valueType: "score",
          hasNotes: true,
        },
      ],
    },
    {
      title: "Overall Evaluation",
      fields: [
        {
          id: "overall",
          label: "Should this candidate proceed to the next stage?",
          valueType: "score",
          hasNotes: true,
        },
      ],
    },
  ],
  behavioral: [
    {
      title: "Team Effectiveness",
      fields: [
        {
          id: "ownership",
          label:
            "Does the candidate take ownership and drive tasks to completion?",
          valueType: "pass_fail",
        },
        {
          id: "communication",
          label:
            "Does the candidate communicate effectively with teammates and managers to resolve issues and align expectations?",
          valueType: "pass_fail",
        },
        {
          id: "execution_quality",
          label: "Execution quality",
          valueType: "score",
          hasNotes: true,
        },
      ],
    },
    {
      title: "Personal Effectiveness",
      fields: [
        {
          id: "prioritization",
          label:
            "Does the candidate prioritize tasks effectively under constraints?",
          valueType: "pass_fail",
        },
        {
          id: "growth",
          label:
            "Has the candidate taken actions outside their comfort zone to learn or grow?",
          valueType: "pass_fail",
        },
        {
          id: "self_development",
          label: "Self-development strength",
          valueType: "score",
          hasNotes: true,
        },
      ],
    },
    {
      title: "Overall Evaluation",
      fields: [
        {
          id: "overall",
          label: "Should this candidate proceed to the next stage?",
          valueType: "score",
          hasNotes: true,
        },
      ],
    },
  ],
  tech: [
    {
      title: "Technical Ability",
      fields: [
        {
          id: "data_structures",
          label:
            "Does the candidate select appropriate data structures and algorithms?",
          valueType: "score",
        },
        {
          id: "correctness",
          label: "How correct and complete is the implementation?",
          valueType: "score",
        },
        {
          id: "debugging",
          label: "How effectively does the candidate identify and fix issues?",
          valueType: "score",
        },
        {
          id: "communication_clarity",
          label:
            "How clearly does the candidate explain their thought process during problem-solving?",
          valueType: "score",
        },
      ],
    },
    {
      title: "Interview Record",
      fields: [
        {
          id: "problem_statement",
          label: "Problem Statement",
          valueType: "notes",
        },
        {
          id: "candidate_approach",
          label: "Candidate Understanding and Approach",
          valueType: "notes",
        },
        { id: "code_snippet", label: "Code Snippet", valueType: "notes" },
      ],
    },
    {
      title: "Overall Evaluation",
      fields: [
        {
          id: "overall",
          label: "Should this candidate proceed to the next stage?",
          valueType: "score",
          hasNotes: true,
        },
      ],
    },
  ],
  board_review: [
    {
      title: "Final Decision",
      fields: [
        {
          id: "final_decision",
          label:
            "Should this candidate proceed to the offer stage / be rejected?",
          valueType: "pass_fail",
          hasNotes: true,
        },
      ],
    },
  ],
};

/**
 * The fixed rubric sections for a stage, or undefined if the stage has none
 * (e.g. "offer", or a terminal stage).
 *
 * @param {string} stage
 * @returns {Array<{title: string, fields: Array<object>}>|undefined}
 */
export const rubricFor = (stage) => RUBRICS[stage];
