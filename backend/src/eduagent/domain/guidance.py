"""Explainable suggestion layer. It never grades, converts reports or assigns.

These categorical product rules are not a calibrated diagnostic scale. The
existing formal policy remains the sole authority for exercise progression.
"""

RULE_VERSION = 'guidance-rules-v1'
REASONS = {
    'pending_diagnosis': '尚无正式答题证据，先通过原练习流程诊断；先验不是诊断结果。',
    'recent_error': '最近一次答错，建议先复习相关资料，再通过原练习流程核验。',
    'below_progress_condition': '现有答题证据尚未满足演示推进条件，可继续复习和练习。',
    'reported_ready_needs_check': '自述能力与当前答题证据可能存在差异，建议进一步诊断；不据此判定任何一方必然错误。',
    'reported_uncertain_despite_evidence': '自述理解与已有作答证据可能不一致，建议回顾作答并进一步核验。',
    'low_confidence': '当前学习信心较低，可以回顾已有成功作答、解释步骤，逐步核验理解。',
    'high_confidence_needs_evidence': '学习信心较高，仍需通过正式答题核验；信心不是正确率。',
    'report_before_latest_attempt': '这份自评早于最近一次正式作答，建议结合新反馈更新自评。',
    'prerequisite_gap': '先修知识点尚未满足现有演示条件，优先核验先修，不建议跳过。',
    'questions_exhausted': '该知识点可用新题已耗尽；先复习资料/历史，保留诊断待办。',
    'round_limit': '已达到原学习流程累计轮数上限；不能通过指南增加新题或绕过限制。',
    'maintain': '当前答题证据满足演示条件，可回顾与巩固；这不证明独立应用能力。',
}


def analyze(items, ordered, goals):
    by_key = {item['knowledge_id']: item for item in items}
    for item in items:
        objective, report = item['objective'], item['self_report']
        evidence = objective['has_evidence']
        codes = []
        if not evidence:
            codes.append('pending_diagnosis')
        elif objective['last_correct'] is False:
            codes.append('recent_error')
        elif not objective['meets_progress_condition']:
            codes.append('below_progress_condition')
        if report:
            if evidence and report['level'] >= 3 and not objective['meets_progress_condition']:
                codes.append('reported_ready_needs_check')
            if objective['meets_progress_condition'] and report['level'] <= 2:
                codes.append('reported_uncertain_despite_evidence')
            if report['confidence'] is not None and report['confidence'] <= 2:
                codes.append('low_confidence')
            if report['confidence'] is not None and report['confidence'] >= 4 and not objective['meets_progress_condition']:
                codes.append('high_confidence_needs_evidence')
            if item['recent_attempts'] and item['recent_attempts'][0]['learning_revision'] > report['learning_revision_at_save']:
                codes.append('report_before_latest_attempt')
        item['blocked_by'] = [key for key in item['prerequisites'] if not by_key[key]['objective']['meets_progress_condition']]
        if item['blocked_by']:
            codes.append('prerequisite_gap')
        if item['round_limit_reached']:
            codes.append('round_limit')
        if item['available_questions'] == 0:
            codes.append('questions_exhausted')
        if not codes:
            codes.append('maintain')
        item.update(reason_codes=codes, reasons=[REASONS[c] for c in codes],
            status='pending_diagnosis' if not evidence else 'needs_review' if not objective['meets_progress_condition'] else 'meets_demo_condition',
            actions=[{'kind': 'open_learning_history', 'knowledge_id': item['knowledge_id']}])
        if not item['blocked_by'] and not item['round_limit_reached'] and item['available_questions']:
            item['actions'].insert(0, {'kind': 'open_formal_practice', 'knowledge_id': item['knowledge_id']})
    candidates = [by_key[key] for key in ordered if not by_key[key]['blocked_by']]
    def rank(item):
        codes = item['reason_codes']
        for priority, group in enumerate((('recent_error',), ('pending_diagnosis',), ('below_progress_condition',),
                ('reported_ready_needs_check', 'reported_uncertain_despite_evidence', 'report_before_latest_attempt'), ('low_confidence',))):
            if any(code in codes for code in group):
                return priority, ordered.index(item['knowledge_id']), item['knowledge_id']
        return 5, ordered.index(item['knowledge_id']), item['knowledge_id']
    candidates.sort(key=rank)
    if candidates and all(rank(item)[0] == 5 for item in candidates):
        candidates = [item for item in candidates if item['knowledge_id'] in goals] or candidates
    return [dict(item, priority=i) for i, item in enumerate(candidates[:3], 1)]


def render_rules(snapshot):
    lines = ['# 个性化学习指南（本地规则）', '',
        f"答题版本 {snapshot['learning_revision']} · 自评版本 {snapshot['assessment_revision']} · {snapshot['rule_version']}",
        '', '学习目标：' + '、'.join(snapshot['goal_names']), '', '以下由程序根据保存学情生成，不代表真实能力测量或学习效果结论。']
    for item in snapshot['recommendations']:
        o, report = item['objective'], item['self_report']
        lines += ['', f"## {item['priority']}. {item['name']}",
            f"正式答题 {o['attempts']} 次；" + (f"BKT模型估计 {o['probability']:.1%}，最近{'答对' if o['last_correct'] else '答错'}。" if o['has_evidence'] else '待诊断，未将先验当作测评结果。'),
            f"我的自评：{report['level']}级；信心：{report['confidence'] if report['confidence'] is not None else '未填写'}；记录时间 {report['created_at']}。" if report else '我的自评：未填写。']
        lines += ['- ' + reason for reason in item['reasons']]
    return '\n'.join(lines)
