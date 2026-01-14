def parse_exam_filter_args(args):
    raw_ids = args.getlist('exam_ids')
    exam_ids = []
    for raw in raw_ids:
        for part in str(raw).split(','):
            part = part.strip()
            if not part:
                continue
            if part.isdigit():
                exam_ids.append(int(part))
    seen = set()
    ordered = []
    for exam_id in exam_ids:
        if exam_id in seen:
            continue
        seen.add(exam_id)
        ordered.append(exam_id)
    filter_requested = args.get('filter')
    filter_active = filter_requested is not None or bool(ordered)
    return ordered, filter_active


def apply_exam_filter(questions, exam_ids, filter_active):
    if not questions:
        return []
    if not filter_active:
        return questions
    if not exam_ids:
        return []
    exam_set = set(exam_ids)
    return [question for question in questions if question.exam_id in exam_set]


def build_exam_options(questions):
    options = []
    seen = set()
    for question in questions:
        exam = question.exam
        if not exam or exam.id in seen:
            continue
        seen.add(exam.id)
        options.append({'id': exam.id, 'title': exam.title})
    return options
