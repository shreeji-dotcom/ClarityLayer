import re
from urllib.parse import quote

import requests
import streamlit as st


# -----------------------------
# Data
# -----------------------------
# -----------------------------
# Data
# -----------------------------
KNOWLEDGE_BASE = {'low hanging fruit': {'simple': 'The easiest task or opportunity to complete first.',
                       'professional': 'A quick win that can be completed with relatively low '
                                       'effort.',
                       'why': 'This usually means the team wants fast progress.',
                       'action': 'Ask which quick win should be prioritized first.',
                       'concepts': ['Prioritization', 'Quick wins', 'Effort vs impact']},
 'kpi': {'simple': 'A number used to measure whether something is working.',
         'professional': 'A key performance indicator used to measure success against a goal.',
         'why': 'KPIs define what success means.',
         'action': 'Ask which KPI matters most and how it is calculated.',
         'concepts': ['Performance measurement', 'Dashboards', 'Metrics']},
 'margin': {'simple': 'The money left after costs are subtracted.',
            'professional': 'Profitability after accounting for revenue and costs.',
            'why': 'Margin shows whether a product, service, or business line is financially '
                   'healthy.',
            'action': 'Ask what cost or revenue driver is affecting margin.',
            'concepts': ['Profitability', 'Cost structure', 'Pricing']},
 'margin compression': {'simple': 'The company is making less profit than before.',
                        'professional': 'Profitability is shrinking because costs increased, '
                                        'prices decreased, or both.',
                        'why': 'This may require pricing, cost, or operational changes.',
                        'action': 'Ask whether the issue is cost-driven, price-driven, or '
                                  'volume-driven.',
                        'concepts': ['Profit erosion', 'Pricing power', 'Cost pressure']},
 'headwinds': {'simple': 'Outside challenges are making progress harder.',
               'professional': 'External market or operational pressures are negatively affecting '
                               'performance.',
               'why': 'This explains why results may be weaker even if the team is working hard.',
               'action': 'Ask which specific external factor is causing pressure.',
               'concepts': ['Market risk', 'Scenario planning', 'External pressure']},
 'leverage': {'simple': 'Use something you already have to get a better result.',
              'professional': 'Use a resource, capability, or relationship to create stronger '
                              'impact.',
              'why': 'The team may need to use existing resources more effectively.',
              'action': 'Ask what should be leveraged and what outcome is expected.',
              'concepts': ['Resources', 'Capabilities', 'Strategic advantage']},
 'stakeholder': {'simple': 'Someone who is affected by or involved in a decision.',
                 'professional': 'A person or group with influence, accountability, or interest in '
                                 'an outcome.',
                 'why': 'Stakeholders can determine whether work moves forward.',
                 'action': 'Ask who needs to be informed, consulted, or approved.',
                 'concepts': ['Stakeholder mapping', 'Decision rights', 'Communication planning']},
 'bandwidth': {'simple': 'How much time or capacity someone has.',
               'professional': 'The available capacity a person or team has to take on work.',
               'why': 'Bandwidth affects whether a request is realistic.',
               'action': 'Ask what should be deprioritized if this becomes urgent.',
               'concepts': ['Capacity planning', 'Workload management', 'Prioritization']},
 'alignment': {'simple': 'Everyone is on the same page.',
               'professional': 'Shared agreement on goals, priorities, assumptions, or direction.',
               'why': 'Without alignment, teams may work toward different goals.',
               'action': 'Ask what decision needs agreement and who must approve it.',
               'concepts': ['Decision-making', 'Governance', 'Communication']},
 'synergy': {'simple': 'Two things work better together than separately.',
             'professional': 'Additional value created when teams, products, or strategies work '
                             'together.',
             'why': 'This is often used to justify partnerships, restructures, or acquisitions.',
             'action': 'Ask what measurable value the combination creates.',
             'concepts': ['Value creation', 'Strategic fit', 'Integration']},
 'circle back': {'simple': 'Talk about this again later.',
                 'professional': 'Revisit the topic after more information, timing clarity, or '
                                 'stakeholder input.',
                 'why': 'The decision may not be ready yet.',
                 'action': 'Ask when to revisit it and what information is needed first.',
                 'concepts': ['Follow-up', 'Decision timing', 'Meeting management']},
 'deep dive': {'simple': 'Look at something more carefully.',
               'professional': 'A detailed analysis of a problem, metric, or decision.',
               'why': 'The issue may need more evidence before action is taken.',
               'action': 'Ask what question the analysis should answer.',
               'concepts': ['Root-cause analysis', 'Data analysis', 'Diagnostics']},
 'action item': {'simple': 'A task someone needs to complete.',
                 'professional': 'A specific follow-up task with ownership and accountability.',
                 'why': 'Action items clarify who is responsible for moving work forward.',
                 'action': 'Ask who owns the task and when it is due.',
                 'concepts': ['Task ownership', 'Accountability', 'Follow-up']},
 'deliverable': {'simple': 'The final thing you are expected to produce.',
                 'professional': 'A concrete output tied to a milestone, project, or business '
                                 'objective.',
                 'why': 'Deliverables define what completion looks like.',
                 'action': 'Ask what format, deadline, and quality standard are expected.',
                 'concepts': ['Project management', 'Milestones', 'Execution']},
 'north star metric': {'simple': 'The most important number the team cares about.',
                       'professional': 'The primary metric that represents long-term success.',
                       'why': 'It helps teams prioritize around one shared definition of success.',
                       'action': 'Ask how the metric is calculated and why it is the priority.',
                       'concepts': ['Strategic metrics', 'Goal alignment', 'Product analytics']},
 'cross-functional': {'simple': 'Multiple teams are working together.',
                      'professional': 'Work that requires coordination across departments or '
                                      'business functions.',
                      'why': 'Cross-functional work can create complexity because ownership is '
                             'shared.',
                      'action': 'Ask which teams are involved and who has final decision '
                                'authority.',
                      'concepts': ['Team coordination',
                                   'Organizational design',
                                   'Decision rights']},
 'buy-in': {'simple': 'People need to agree with or support the idea.',
            'professional': 'Stakeholder support needed for adoption, approval, funding, or '
                            'execution.',
            'why': 'Without buy-in, good ideas may not move forward.',
            'action': 'Ask whose support is needed and what concerns must be addressed.',
            'concepts': ['Influence', 'Change management', 'Stakeholder support']},
 'roadmap': {'simple': 'A plan for what will happen next and when.',
             'professional': 'A forward-looking plan showing priorities, timing, and milestones.',
             'why': 'Roadmaps help teams understand sequencing and tradeoffs.',
             'action': 'Ask which items are committed, tentative, or dependent on other work.',
             'concepts': ['Planning', 'Prioritization', 'Project sequencing']},
 'blocker': {'simple': 'Something stopping work from moving forward.',
             'professional': 'A constraint, dependency, or risk preventing execution.',
             'why': 'Blockers must be resolved before progress can continue.',
             'action': 'Ask what is blocked, who can unblock it, and by when.',
             'concepts': ['Dependencies', 'Risk management', 'Execution barriers']},
 'dependency': {'simple': 'Something that must happen before another task can move forward.',
                'professional': 'A prerequisite task, resource, approval, or decision needed for '
                                'execution.',
                'why': 'Dependencies affect timing, ownership, and project risk.',
                'action': 'Ask what the dependency is and who owns it.',
                'concepts': ['Project planning', 'Sequencing', 'Risk']},
 'scope': {'simple': 'What is included or not included in the project.',
           'professional': 'The defined boundaries, deliverables, and constraints of a project.',
           'why': 'Unclear scope can cause extra work, delays, and confusion.',
           'action': 'Ask what is included, excluded, and out of scope.',
           'concepts': ['Project scope', 'Requirements', 'Expectation setting']},
 'out of scope': {'simple': 'Not part of what you are supposed to work on right now.',
                  'professional': 'Outside the approved project boundaries or current '
                                  'responsibility.',
                  'why': 'This prevents extra work from being added without agreement.',
                  'action': 'Ask whether it should be excluded, deferred, or formally added.',
                  'concepts': ['Scope control', 'Prioritization', 'Project governance']},
 'root cause': {'simple': 'The real reason behind the problem.',
                'professional': 'The underlying driver of a problem, not just the visible symptom.',
                'why': 'Solving symptoms without fixing root causes can make the issue return.',
                'action': 'Ask what evidence points to the root cause.',
                'concepts': ['Problem solving', 'Diagnostics', 'Root-cause analysis']},
 'pain point': {'simple': 'A problem or frustration someone experiences.',
                'professional': 'A recurring friction point affecting users, customers, employees, '
                                'or operations.',
                'why': 'Pain points show where improvement can create value.',
                'action': 'Ask who experiences the pain point and how severe it is.',
                'concepts': ['User needs', 'Customer experience', 'Process improvement']},
 'value prop': {'simple': 'Why someone should care about or use something.',
                'professional': 'The core value proposition explaining the benefit delivered to a '
                                'target audience.',
                'why': 'A clear value prop helps people understand why something matters.',
                'action': 'Ask who the audience is and what benefit they receive.',
                'concepts': ['Positioning', 'Customer benefits', 'Value proposition']},
 'tradeoff': {'simple': 'Choosing one thing means giving up something else.',
              'professional': 'A decision involving competing priorities, constraints, or '
                              'opportunity costs.',
              'why': 'Tradeoffs clarify what the team is prioritizing.',
              'action': 'Ask what is being prioritized and what is being sacrificed.',
              'concepts': ['Opportunity cost', 'Prioritization', 'Strategic decision-making']},
 'runway': {'simple': 'How much time or money remains before resources run out.',
            'professional': 'The remaining operating time or funding available before a constraint '
                            'is reached.',
            'why': 'Runway affects urgency, risk, and planning.',
            'action': 'Ask what assumptions the runway is based on.',
            'concepts': ['Financial planning', 'Resource constraints', 'Startup finance']},
 'asap': {'simple': 'As soon as possible.',
          'professional': 'A vague urgency signal that may need a specific deadline.',
          'why': 'ASAP can create stress because it does not define an actual timeline.',
          'action': 'Ask what deadline or priority level is expected.',
          'concepts': ['Time management', 'Priority setting', 'Communication clarity']},
 'visibility': {'simple': 'People can see or track what is happening.',
                'professional': 'Awareness or transparency into work, progress, risk, or '
                                'performance.',
                'why': 'Visibility helps leaders monitor progress and make decisions.',
                'action': 'Ask who needs visibility and what format they need.',
                'concepts': ['Reporting', 'Transparency', 'Status updates']},
 'escalate': {'simple': 'Bring the issue to someone higher up.',
              'professional': 'Raise an issue to a manager, leader, or decision-maker for '
                              'resolution.',
              'why': 'Escalation usually means the issue cannot be solved at the current level.',
              'action': 'Ask who it should be escalated to and what information they need.',
              'concepts': ['Issue management', 'Decision rights', 'Leadership communication']},
 'pushback': {'simple': 'Someone disagrees or has concerns.',
              'professional': 'Resistance, concern, or disagreement from a person or group.',
              'why': 'Pushback may signal risk, misalignment, or missing context.',
              'action': 'Ask what concern is driving the pushback.',
              'concepts': ['Conflict management', 'Stakeholder concerns', 'Change resistance']},
 'business case': {'simple': 'The reason something is worth doing.',
                   'professional': 'A justification for an initiative based on expected value, '
                                   'cost, risk, and impact.',
                   'why': 'A business case helps decision-makers decide whether to approve work.',
                   'action': 'Ask what benefit, cost, and risk should be included.',
                   'concepts': ['ROI', 'Feasibility', 'Strategic justification']},
 'roi': {'simple': 'Whether the benefit is worth the cost.',
         'professional': 'Return on investment, measuring gain relative to cost.',
         'why': 'ROI helps compare whether an initiative is financially worthwhile.',
         'action': 'Ask how benefits and costs are being calculated.',
         'concepts': ['Financial analysis', 'Investment evaluation', 'Cost-benefit analysis']},
 'burn rate': {'simple': 'How quickly money is being spent.',
               'professional': 'The rate at which a company or project consumes available cash.',
               'why': 'Burn rate affects runway and financial risk.',
               'action': 'Ask what expenses are driving the burn rate.',
               'concepts': ['Cash flow', 'Startup finance', 'Expense management']},
 'churn': {'simple': 'Customers or employees leaving.',
           'professional': 'The rate at which customers, users, or employees stop participating.',
           'why': 'High churn can signal dissatisfaction, weak retention, or poor fit.',
           'action': 'Ask what segment is churning and why.',
           'concepts': ['Retention', 'Customer analytics', 'Employee turnover']},
 'retention': {'simple': 'Keeping customers, users, or employees over time.',
               'professional': 'The ability to maintain continued engagement, usage, or '
                               'employment.',
               'why': 'Retention often matters more than one-time acquisition.',
               'action': 'Ask which retention metric is being tracked.',
               'concepts': ['Customer loyalty', 'Employee retention', 'Engagement']},
 'conversion': {'simple': 'When someone takes the desired action.',
                'professional': 'The percentage of users or customers who complete a target '
                                'action.',
                'why': 'Conversion shows whether a process, campaign, or product flow is working.',
                'action': 'Ask what action counts as conversion.',
                'concepts': ['Marketing funnel', 'User behavior', 'Performance analytics']},
 'funnel': {'simple': 'The steps someone goes through before taking action.',
            'professional': 'A staged process that tracks movement from awareness to conversion.',
            'why': 'Funnels help identify where people drop off.',
            'action': 'Ask which stage has the biggest drop-off.',
            'concepts': ['Customer journey', 'Marketing analytics', 'Conversion optimization']},
 'pipeline': {'simple': 'A list of future opportunities or work moving through stages.',
              'professional': 'A structured flow of opportunities, tasks, deals, or candidates '
                              'through defined stages.',
              'why': 'Pipeline health helps teams forecast future outcomes.',
              'action': 'Ask what stage the item is in and what moves it forward.',
              'concepts': ['Sales pipeline', 'Workflow management', 'Forecasting']},
 'forecast': {'simple': 'A prediction about what will happen.',
              'professional': 'An estimate of future performance based on assumptions, trends, or '
                              'data.',
              'why': 'Forecasts support planning, budgeting, and resource decisions.',
              'action': 'Ask what assumptions the forecast depends on.',
              'concepts': ['Forecasting', 'Scenario analysis', 'Planning']},
 'variance': {'simple': 'The difference between expected and actual results.',
              'professional': 'A gap between planned, forecasted, budgeted, or actual performance.',
              'why': 'Variance helps identify where performance is off track.',
              'action': 'Ask what caused the variance and whether action is needed.',
              'concepts': ['Budgeting', 'Performance analysis', 'Variance analysis']},
 'baseline': {'simple': 'The starting point used for comparison.',
              'professional': 'A reference point used to measure change, improvement, or '
                              'performance.',
              'why': 'Without a baseline, it is hard to know whether results improved.',
              'action': 'Ask what baseline is being used.',
              'concepts': ['Benchmarking', 'Measurement', 'Performance tracking']},
 'okr': {'simple': 'A goal and the measurable results tied to it.',
         'professional': 'Objectives and Key Results framework used to align priorities and track '
                         'progress.',
         'why': 'OKRs clarify what the team is trying to achieve and how success is measured.',
         'action': 'Ask what the objective is and which key result is lagging.',
         'concepts': ['Goal setting', 'Performance measurement', 'Alignment']},
 'sla': {'simple': 'A promised response or delivery time.',
         'professional': 'Service Level Agreement defining expected service standards and '
                         'timelines.',
         'why': 'SLAs set expectations for speed, reliability, and accountability.',
         'action': 'Ask which SLA target applies and whether it is being met.',
         'concepts': ['Operations', 'Customer support', 'Service quality']},
 'mvp': {'simple': 'The smallest usable version of a product.',
         'professional': 'Minimum Viable Product built with core features to validate demand '
                         'quickly.',
         'why': 'MVPs reduce risk by testing assumptions before full investment.',
         'action': 'Ask which core feature must be proven in the MVP.',
         'concepts': ['Product strategy', 'Experimentation', 'Lean development']},
 'stakeholder management': {'simple': 'Keeping key people informed and aligned.',
                            'professional': 'Structured engagement strategy for influential '
                                            'parties across a project lifecycle.',
                            'why': 'Poor stakeholder management creates delays, rework, and '
                                   'resistance.',
                            'action': 'Ask which stakeholders need active updates and decision '
                                      'support.',
                            'concepts': ['Communication', 'Governance', 'Influence']},
 'single source of truth': {'simple': 'One trusted place for the latest information.',
                            'professional': 'A central authoritative data source used for '
                                            'consistent decision-making.',
                            'why': 'Multiple versions of data can lead to conflicting decisions.',
                            'action': 'Ask which source should be treated as authoritative.',
                            'concepts': ['Data governance', 'Reporting', 'Analytics']},
 'kickoff': {'simple': 'The first meeting to start a project.',
             'professional': 'Initial alignment session to confirm scope, owners, timeline, and '
                             'success criteria.',
             'why': 'A strong kickoff reduces ambiguity early in execution.',
             'action': 'Ask what decisions must be finalized in kickoff.',
             'concepts': ['Project management', 'Planning', 'Alignment']},
 'postmortem': {'simple': 'Reviewing what went wrong and why.',
                'professional': 'Structured retrospective analysis after an incident or project '
                                'outcome.',
                'why': 'Postmortems turn failures into repeatable learning.',
                'action': 'Ask which root causes and prevention actions were identified.',
                'concepts': ['Continuous improvement', 'Incident management', 'Learning culture']},
 'cadence': {'simple': 'How often something happens.',
             'professional': 'A recurring operating rhythm for meetings, reporting, or execution '
                             'cycles.',
             'why': 'Cadence creates predictability and keeps teams synchronized.',
             'action': 'Ask what cadence is expected and who owns updates.',
             'concepts': ['Operating rhythm', 'Team coordination', 'Execution']},
 'narrative': {'simple': 'The main story or explanation.',
               'professional': 'A structured strategic storyline that explains data, context, and '
                               'decisions.',
               'why': 'A clear narrative helps stakeholders understand and support '
                      'recommendations.',
               'action': 'Ask what core message the narrative should communicate.',
               'concepts': ['Executive communication', 'Strategy', 'Storytelling']},
 'swimlane': {'simple': 'A category showing who owns what work.',
              'professional': 'A process-mapping lane that groups tasks by function, team, or '
                              'owner.',
              'why': 'Swimlanes make ownership boundaries and handoffs explicit.',
              'action': 'Ask which swimlane owns the current blocker.',
              'concepts': ['Process design', 'Ownership', 'Workflow']},
 'raci': {'simple': 'A chart showing who does, approves, contributes, and stays informed.',
          'professional': 'Responsibility assignment matrix defining Responsible, Accountable, '
                          'Consulted, and Informed roles.',
          'why': 'RACI prevents confusion around ownership and decision rights.',
          'action': 'Ask who is accountable and who must be consulted before decisions.',
          'concepts': ['Governance', 'Decision rights', 'Project roles']},
 'change request': {'simple': 'A formal ask to modify scope or plan.',
                    'professional': 'A documented proposal to alter approved project scope, '
                                    'timeline, or deliverables.',
                    'why': 'Change requests protect teams from unmanaged scope growth.',
                    'action': 'Ask whether this should be logged as a formal change request.',
                    'concepts': ['Scope control', 'Project governance', 'Change management']},
 'backlog': {'simple': 'A list of pending work items.',
             'professional': 'A prioritized queue of tasks, enhancements, or issues awaiting '
                             'execution.',
             'why': 'Backlog quality shapes delivery focus and team throughput.',
             'action': 'Ask where this item sits in backlog priority.',
             'concepts': ['Agile delivery', 'Prioritization', 'Execution planning']},
 'tech debt': {'simple': 'Shortcuts in systems that cause extra work later.',
               'professional': 'Accumulated engineering compromises that increase future '
                               'maintenance and risk.',
               'why': 'Tech debt can slow delivery and increase defects over time.',
               'action': 'Ask whether this issue is caused by known tech debt.',
               'concepts': ['Engineering quality', 'Maintainability', 'Risk management']},
 'runbook': {'simple': 'A step-by-step guide for handling tasks or incidents.',
             'professional': 'Operational documentation outlining procedures, escalation paths, '
                             'and recovery steps.',
             'why': 'Runbooks reduce response time and improve consistency under pressure.',
             'action': 'Ask whether a runbook exists for this scenario.',
             'concepts': ['Operations', 'Incident response', 'Standardization']}}

EXAMPLES = ['We need to leverage low hanging fruit to improve KPI performance despite market headwinds.',
 'Margin compression is affecting SKU-level profitability, so we need a deep dive before '
 'leadership review.',
 'The team has limited bandwidth, so we need stakeholder alignment before moving forward.',
 'Let’s circle back after we identify synergy opportunities and optimize execution.',
 'We need a stronger business case before escalating this to stakeholders.',
 'The forecast shows unfavorable variance, but we need a baseline before drawing conclusions.',
 'Churn is increasing in the funnel, so we need to identify the biggest conversion blocker.']

BLOCKED_LANGUAGE = {'shut up', 'dumb', 'idiot', 'moron', 'hate you', 'stupid'}


# -----------------------------
# Analysis Helpers
# -----------------------------
def contains_inappropriate_language(text: str, blocked_language: set[str]) -> bool:
    lowered = text.lower()
    return any(bad_word in lowered for bad_word in blocked_language)


def detect_terms(text: str, knowledge_base: dict) -> dict:
    lower_text = text.lower()
    matched = {}
    for term in sorted(knowledge_base.keys(), key=len, reverse=True):
        if term in lower_text:
            matched[term] = knowledge_base[term]
    return matched


def lookup_acronym_meaning(term: str) -> dict | None:
    clean = term.strip()
    if not clean:
        return None

    wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(clean)}"
    try:
        wiki_resp = requests.get(wiki_url, timeout=4)
        if wiki_resp.ok:
            wiki_data = wiki_resp.json()
            extract = wiki_data.get("extract")
            if extract:
                return {
                    "simple": extract.split(".")[0].strip() + ".",
                    "professional": extract.strip(),
                    "why": "This definition was fetched from an external source because it was not in the local glossary.",
                    "action": "Ask whether this external definition matches your company context.",
                    "concepts": ["External lookup", "Acronym context", "Knowledge expansion"],
                    "source": "Wikipedia",
                }
    except requests.RequestException:
        pass

    ddg_url = f"https://api.duckduckgo.com/?q={quote(clean + ' acronym meaning')}&format=json&no_html=1"
    try:
        ddg_resp = requests.get(ddg_url, timeout=4)
        if ddg_resp.ok:
            ddg_data = ddg_resp.json()
            abstract = ddg_data.get("AbstractText")
            if abstract:
                return {
                    "simple": abstract.split(".")[0].strip() + ".",
                    "professional": abstract.strip(),
                    "why": "This definition was fetched from an external source because it was not in the local glossary.",
                    "action": "Ask whether this external definition matches your company context.",
                    "concepts": ["External lookup", "Acronym context", "Knowledge expansion"],
                    "source": "DuckDuckGo",
                }
    except requests.RequestException:
        pass

    return None


def enrich_with_external_acronyms(text: str, matched_terms: dict, knowledge_base: dict) -> dict:
    acronyms = set(re.findall(r"\b[A-Z]{2,10}\b", text))
    enriched = dict(matched_terms)
    for acronym in acronyms:
        key = acronym.lower()
        if key in knowledge_base or key in enriched:
            continue
        payload = lookup_acronym_meaning(acronym)
        if payload:
            enriched[key] = payload
    return enriched


def count_sentences(text: str) -> int:
    sentences = re.split(r"[.!?]+", text)
    return len([s for s in sentences if s.strip()])


def calculate_scores(text: str, matched_terms: dict) -> dict:
    words = text.split()
    word_count = len(words)
    sentence_count = count_sentences(text)
    detected_terms = len(matched_terms)
    avg_words_per_sentence = round(word_count / max(sentence_count, 1), 1)
    jargon_density = round((detected_terms / max(word_count, 1)) * 100, 1)

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "detected_terms": detected_terms,
        "avg_words_per_sentence": avg_words_per_sentence,
        "jargon_density": min(jargon_density, 100),
    }


def build_translation(matched_terms: dict, explanation_style: str) -> str:
    if not matched_terms:
        return (
            "This message does not contain major terms from the current database, "
            "but it may still require context about the goal, owner, deadline, or expected action."
        )

    lines = []
    for term, data in matched_terms.items():
        meaning = data["simple"] if explanation_style == "Plain language" else data["professional"]
        lines.append(f"**{term}**: {meaning}")
    return "\n\n".join(lines)


def hidden_assumptions(matched_terms: dict) -> list[str]:
    assumptions = []
    if "kpi" in matched_terms or "north star metric" in matched_terms:
        assumptions.append("This assumes you know which metric matters most and how it is measured.")
    if "margin" in matched_terms or "margin compression" in matched_terms:
        assumptions.append("This assumes you understand the financial driver behind the issue.")
    if "stakeholder" in matched_terms or "buy-in" in matched_terms:
        assumptions.append("This assumes you know whose approval or support is required.")
    if "bandwidth" in matched_terms:
        assumptions.append("This assumes capacity is limited and priorities may need to shift.")
    if "alignment" in matched_terms:
        assumptions.append("This assumes there is uncertainty or disagreement that needs to be resolved.")
    if "dependency" in matched_terms or "blocker" in matched_terms:
        assumptions.append("This assumes progress depends on something outside the current task.")
    if "forecast" in matched_terms or "variance" in matched_terms:
        assumptions.append("This assumes you know the baseline, assumptions, and expected performance.")

    if not assumptions:
        assumptions = [
            "The message may assume shared background knowledge.",
            "The expected action may not be fully stated.",
            "The owner, deadline, or success metric may need clarification.",
        ]
    return assumptions


def suggested_questions(matched_terms: dict) -> list[str]:
    questions = []
    for term, data in matched_terms.items():
        questions.append(f"What does **{term}** mean in this specific context?")
        questions.append(data["action"])

    if not questions:
        questions = [
            "What does this mean in simpler terms?",
            "What is the expected next step?",
            "Who owns the decision?",
            "What deadline should I work toward?",
        ]

    questions.insert(0, "Could you clarify the main priority so I can make sure I’m aligned?")
    return list(dict.fromkeys(questions))[:10]


def learn_more(matched_terms: dict) -> list[str]:
    concepts = []
    for data in matched_terms.values():
        concepts.extend(data["concepts"])
    return list(dict.fromkeys(concepts or ["Workplace communication", "Business context", "Clarifying questions"]))[:10]


def follow_up_message(matched_terms: dict) -> str:
    if matched_terms:
        return (
            "Thanks for the context. To make sure I’m aligned, could you clarify the main priority, "
            "the expected outcome, and whether there is a specific owner, deadline, or metric I should focus on?"
        )
    return (
        "Thanks for sharing this. Could you clarify what the expected next step is, who owns it, "
        "and whether there is a specific deadline or success measure I should keep in mind?"
    )


def meeting_response(matched_terms: dict) -> str:
    if matched_terms:
        return (
            "That makes sense. To make sure I’m understanding correctly, can we clarify the priority, "
            "the metric or outcome we are optimizing for, and who owns the next step?"
        )
    return "That makes sense. Could we clarify the expected outcome and next step before I move forward?"


def simplify_message(text: str, matched_terms: dict) -> str:
    simplified = text
    for term in sorted(matched_terms.keys(), key=len, reverse=True):
        plain = matched_terms[term]["simple"]
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        simplified = pattern.sub(f"{term} ({plain})", simplified)
    return simplified


def build_layman_summary(original_text: str, matched_terms: dict) -> str:
    """Create a practical explanation of what the message likely means."""
    if not matched_terms:
        return (
            "This message likely means someone wants progress, but key context is missing. "
            "In plain terms: confirm the top priority, who owns next steps, and when decisions are due."
        )

    terms = list(matched_terms.keys())[:4]
    plain_meanings = [matched_terms[t]["simple"].rstrip(".") for t in terms]
    why_it_matters = [matched_terms[t]["why"].rstrip(".") for t in terms[:2]]
    actions = [matched_terms[t]["action"].rstrip(".") for t in terms[:2]]

    return (
        f"What this likely means: the message is focused on {', '.join(terms)}. "
        f"In everyday language: {'; '.join(plain_meanings)}. "
        f"Why this matters now: {'; '.join(why_it_matters)}. "
        f"What you should ask next: {'; '.join(actions)}."
    )


def generate_chat_reply(user_question: str, analysis_result: dict, explanation_style: str) -> str:
    matched_terms = analysis_result.get("matched_terms", {})
    lower_question = user_question.lower()

    if any(token in lower_question for token in ["summarize", "summary", "overall", "main point"]):
        return build_layman_summary(analysis_result["user_input"], matched_terms)
    if any(token in lower_question for token in ["question", "ask", "clarify"]):
        return "Here are useful follow-up questions:\n- " + "\n- ".join(suggested_questions(matched_terms)[:3])
    for term, data in matched_terms.items():
        if term in lower_question:
            meaning = data["simple"] if explanation_style == "Plain language" else data["professional"]
            return f"**{term}** means: {meaning}\n\nWhy it matters: {data['why']}\n\nYou can ask: {data['action']}"
    if any(token in lower_question for token in ["next step", "what do i do", "response"]):
        return follow_up_message(matched_terms)
    return "I can explain terms, summarize, or suggest follow-up questions."


def role_based_interpretation(role: str) -> str:
    if role == "New employee / intern":
        return "Focus on understanding terms, expected action, deadlines, and who can clarify context."
    if role == "Analyst":
        return "Focus on metric, data source, driver, baseline, and decision implications."
    if role == "Manager":
        return "Focus on ownership, resource constraints, sequencing, alignment, and execution risk."
    return "Focus on strategic implications, stakeholder alignment, tradeoffs, risk, and measurable impact."


# -----------------------------
# UI Helpers
# -----------------------------
def inject_styles() -> None:
    st.markdown("""
    <style>
    .stApp { background: linear-gradient(180deg, #f8fbff 0%, #f3f7ff 30%, #ffffff 100%); }
    .hero-card { border: 1px solid #d9e4ff; background: linear-gradient(120deg, #12254a 0%, #1f3a71 55%, #244b94 100%); border-radius: 18px; padding: 1.2rem 1.4rem; color: #f5f8ff; margin-bottom: 1rem; }
    .pill-row { margin-top: 0.8rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .pill { border: 1px solid rgba(255,255,255,0.3); border-radius: 999px; padding: 0.22rem 0.7rem; font-size: 0.8rem; background: rgba(255,255,255,0.08); }
    .term-card { border: 1px solid #d8e3ff; border-radius: 14px; background: #fff; padding: 0.9rem 1rem; margin-bottom: 0.8rem; overflow-wrap:anywhere; }
    div[role=\"radiogroup\"] { gap: 0.75rem !important; }
    div[role=\"radiogroup\"] > label { padding: 0.2rem 0.55rem; border-radius: 999px; border: 1px solid #c8d8ff; background: #f7faff; }
    </style>
    """, unsafe_allow_html=True)


def render_wrapped_card(title: str, text: str) -> None:
    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.markdown(f"<div style='white-space: pre-wrap; line-height: 1.6'>{text}</div>", unsafe_allow_html=True)


def render_clickable_terms(matched_terms: dict) -> None:
    if not matched_terms:
        st.write("No major known jargon terms were detected.")
        return
    terms = list(matched_terms.keys())
    cols = st.columns(min(4, len(terms)))
    for i, term in enumerate(terms):
        if cols[i % len(cols)].button(term, key=f"term_btn_{term}"):
            st.session_state["selected_term"] = term
    selected = st.session_state.get("selected_term", terms[0])
    if selected not in matched_terms:
        selected = terms[0]
    d = matched_terms[selected]
    source = f"<div><b>Source:</b> {d['source']}</div>" if d.get("source") else ""
    st.markdown(f"<div class='term-card'><h4>{selected}</h4><div><b>Plain:</b> {d['simple']}</div><div><b>Professional:</b> {d['professional']}</div><div><b>Why:</b> {d['why']}</div><div><b>Action:</b> {d['action']}</div>{source}</div>", unsafe_allow_html=True)


def render_section_selector() -> str:
    return st.radio(
        "Report Sections",
        ["Hidden Meaning", "Questions", "Learn More", "Response Generator", "Web Lookup"],
        horizontal=True,
        key="active_section",
        label_visibility="collapsed",
    )


# -----------------------------
# App
# -----------------------------
st.set_page_config(page_title="ClarityLayer", page_icon="🧠", layout="wide")

# Session defaults (expanded for readability)
SESSION_DEFAULTS = {
    "custom_terms": {},
    "draft_input": "",
    "analysis_result": None,
    "active_section": "Hidden Meaning",
    "chat_history": [],
    "web_lookup_result": None,
}

for key, default in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

inject_styles()

# Sidebar controls
with st.sidebar:
    st.markdown("## 🧠 ClarityLayer")
    explanation_style = st.radio(
        "Explanation style",
        ["Plain language", "Professional"],
        index=0,
    )
    role = st.selectbox(
        "User perspective",
        ["New employee / intern", "Analyst", "Manager", "Executive"],
    )
    web_lookup_enabled = st.toggle("Search web for unknown acronyms", value=True)
    st.info("External acronym lookup uses public web sources when enabled.")

st.markdown(
    """
    <div class='hero-card'>
        <p><b>🧠 ClarityLayer</b></p>
        <div>Elevated clarity assistant for workplace language.</div>
        <div class='pill-row'>
            <span class='pill'>Privacy-first</span>
            <span class='pill'>Session-only custom terms</span>
            <span class='pill'>Optional web acronym lookup</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Custom-term editor
with st.expander("➕ Add your own term or acronym (session only)"):
    with st.form("custom_term_form", clear_on_submit=True):
        term = st.text_input("Term or acronym")
        simple = st.text_area("Plain meaning")
        professional = st.text_area("Professional meaning")
        why = st.text_area("Why it matters")
        action = st.text_input("Recommended clarifying action")
        concepts_text = st.text_input("Concept tags (comma-separated)")
        submitted = st.form_submit_button("Save term")

    if submitted and term.strip() and simple.strip() and professional.strip() and action.strip():
        clean_term = term.strip().lower()
        concept_list = [c.strip() for c in concepts_text.split(",") if c.strip()]

        if not concept_list:
            concept_list = ["Custom terminology"]

        st.session_state["custom_terms"][clean_term] = {
            "simple": simple.strip(),
            "professional": professional.strip(),
            "why": why.strip() or "Needs context.",
            "action": action.strip(),
            "concepts": concept_list,
        }

st.text_area(
    "Paste workplace language, meeting notes, or an email.",
    height=220,
    key="draft_input",
)

if st.button("Analyze with ClarityLayer", type="primary"):
    user_input = st.session_state["draft_input"]
    knowledge_base = {**KNOWLEDGE_BASE, **st.session_state["custom_terms"]}
    if not user_input.strip():
        st.warning("Please enter some workplace language first.")
        st.session_state["analysis_result"] = None
    elif contains_inappropriate_language(user_input, BLOCKED_LANGUAGE):
        st.error("Please remove inappropriate language and try again.")
        st.session_state["analysis_result"] = None
    else:
        matched_terms = detect_terms(user_input, knowledge_base)
        if web_lookup_enabled:
            matched_terms = enrich_with_external_acronyms(
                user_input,
                matched_terms,
                knowledge_base,
            )

        scores = calculate_scores(user_input, matched_terms)
        st.session_state["analysis_result"] = {
            "user_input": user_input,
            "matched_terms": matched_terms,
            "scores": scores,
        }
        st.session_state["chat_history"] = []

analysis_result = st.session_state.get("analysis_result")
if analysis_result:
    user_input = analysis_result["user_input"]
    matched_terms = analysis_result["matched_terms"]
    scores = analysis_result["scores"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Word Count", scores["word_count"])
    c2.metric("Sentence Count", scores["sentence_count"])
    c3.metric("Detected Terms", scores["detected_terms"])
    c4.metric("Avg Words / Sentence", scores["avg_words_per_sentence"])

    section = render_section_selector()
    if section == "Hidden Meaning":
        render_clickable_terms(matched_terms)
        for item in hidden_assumptions(matched_terms):
            st.write(f"- {item}")
        st.write(role_based_interpretation(role))
    elif section == "Questions":
        for q in suggested_questions(matched_terms):
            st.write(f"- {q}")
    elif section == "Learn More":
        for concept in learn_more(matched_terms):
            st.write(f"- {concept}")
    elif section == "Response Generator":
        st.text_area("Copy/edit this message:", value=follow_up_message(matched_terms), height=120)
        st.text_area("Meeting response:", value=meeting_response(matched_terms), height=100)
    else:
        st.markdown("### 🌐 Online Acronym/Term Lookup")
        with st.form("web_lookup_form"):
            lookup_query = st.text_input(
                "Search a term online",
                placeholder="Example: EBITDA",
                key="web_lookup_query",
            )
            lookup_submitted = st.form_submit_button("Search online")

        if lookup_submitted:
            if lookup_query.strip():
                external_result = lookup_acronym_meaning(lookup_query.strip())
                st.session_state["web_lookup_result"] = external_result or {"not_found": True}
            else:
                st.session_state["web_lookup_result"] = {"error": "Type a term or acronym to search."}

        web_result = st.session_state.get("web_lookup_result")
        if web_result:
            if web_result.get("error"):
                st.info(web_result["error"])
            elif web_result.get("not_found"):
                st.warning("No external meaning found for that term.")
            else:
                render_wrapped_card(
                    f"Result ({web_result.get('source', 'External source')})",
                    web_result.get("professional", "No description returned."),
                )

    st.markdown("### 💬 Clarity Chat")
    for m in st.session_state["chat_history"]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    prompt = st.chat_input("Ask a follow-up question")
    if prompt:
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        reply = generate_chat_reply(prompt, analysis_result, explanation_style)
        st.session_state["chat_history"].append({"role": "assistant", "content": reply})
        st.rerun()
