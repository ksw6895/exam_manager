(function () {
    'use strict';

    var PRACTICE_VERSION = 1;
    var SEOUL_OFFSET_MINUTES = 9 * 60;

    function nowISO() {
        var now = Date.now();
        var seoul = new Date(now + SEOUL_OFFSET_MINUTES * 60 * 1000);
        return seoul.toISOString().replace('Z', '+09:00');
    }

    function getPracticeKey(lectureId) {
        return 'practice_' + lectureId;
    }

    function getPracticeResultKey(lectureId) {
        return getPracticeKey(lectureId) + '_result';
    }

    function buildEmptyState(lectureId) {
        return {
            version: PRACTICE_VERSION,
            lectureId: lectureId,
            updatedAt: nowISO(),
            answers: {}
        };
    }

    function isNumericKey(key) {
        return /^[0-9]+$/.test(String(key));
    }

    function getMetaType(questionId, questionMetaMap) {
        if (!questionMetaMap) return null;
        if (questionMetaMap.hasOwnProperty(questionId)) {
            return questionMetaMap[questionId] ? 'short' : 'mcq';
        }
        return null;
    }

    function normalizeMcqValue(value) {
        if (Array.isArray(value)) {
            var nums = value
                .map(function (v) { return parseInt(v, 10); })
                .filter(function (v) { return Number.isFinite(v); });
            return nums.length > 0 ? nums : null;
        }
        if (typeof value === 'number') {
            return Number.isFinite(value) ? [value] : null;
        }
        if (typeof value === 'string') {
            var trimmed = value.trim();
            if (!trimmed) return null;
            var parts = trimmed.split(',').map(function (v) { return parseInt(v, 10); })
                .filter(function (v) { return Number.isFinite(v); });
            return parts.length > 0 ? parts : null;
        }
        return null;
    }

    function normalizeShortValue(value) {
        if (value === null || value === undefined) return null;
        if (Array.isArray(value)) {
            if (value.length === 0) return null;
            return String(value.join(','));
        }
        var str = String(value);
        return str.trim() === '' ? null : str;
    }

    function normalizeAnswerEntry(questionId, rawValue, questionMetaMap, preferMeta) {
        if (rawValue === null || rawValue === undefined) return null;

        var value = rawValue;
        if (rawValue && typeof rawValue === 'object' && rawValue.hasOwnProperty('value')) {
            value = rawValue.value;
        }

        var type = null;
        if (preferMeta) {
            type = getMetaType(questionId, questionMetaMap);
        }
        if (!type && rawValue && typeof rawValue === 'object' && rawValue.type) {
            if (rawValue.type === 'mcq' || rawValue.type === 'short') {
                type = rawValue.type;
            }
        }
        if (!type) {
            if (Array.isArray(value) || typeof value === 'number') {
                type = 'mcq';
            } else if (typeof value === 'string') {
                type = 'short';
            }
        }

        if (type === 'mcq') {
            var mcqValue = normalizeMcqValue(value);
            return mcqValue ? { type: 'mcq', value: mcqValue } : null;
        }
        if (type === 'short') {
            var shortValue = normalizeShortValue(value);
            return shortValue ? { type: 'short', value: shortValue } : null;
        }
        return null;
    }

    function migrateLegacyAnswers(rawAnswers, questionMetaMap) {
        var normalized = {};
        if (!rawAnswers || typeof rawAnswers !== 'object') return normalized;

        Object.keys(rawAnswers).forEach(function (key) {
            if (!isNumericKey(key)) return;
            var entry = normalizeAnswerEntry(key, rawAnswers[key], questionMetaMap, true);
            if (entry) {
                normalized[String(key)] = entry;
            }
        });

        return normalized;
    }

    function normalizeV1Answers(rawAnswers) {
        var normalized = {};
        if (!rawAnswers || typeof rawAnswers !== 'object') return normalized;

        Object.keys(rawAnswers).forEach(function (key) {
            if (!isNumericKey(key)) return;
            var entry = normalizeAnswerEntry(key, rawAnswers[key], null, false);
            if (entry) {
                normalized[String(key)] = entry;
            }
        });

        return normalized;
    }

    function loadPracticeState(lectureId, questionMetaMap) {
        var key = getPracticeKey(lectureId);
        var raw = localStorage.getItem(key);
        if (!raw) {
            return buildEmptyState(lectureId);
        }

        var parsed;
        try {
            parsed = JSON.parse(raw);
        } catch (e) {
            return buildEmptyState(lectureId);
        }

        if (parsed && parsed.version === PRACTICE_VERSION && parsed.answers) {
            return {
                version: PRACTICE_VERSION,
                lectureId: parsed.lectureId || lectureId,
                updatedAt: parsed.updatedAt || nowISO(),
                answers: normalizeV1Answers(parsed.answers)
            };
        }

        var legacyAnswers = null;
        if (parsed && typeof parsed === 'object') {
            if (parsed.answers && typeof parsed.answers === 'object') {
                legacyAnswers = parsed.answers;
            } else {
                legacyAnswers = parsed;
            }
        }

        var migrated = buildEmptyState(lectureId);
        migrated.answers = migrateLegacyAnswers(legacyAnswers, questionMetaMap);
        savePracticeState(migrated);
        return migrated;
    }

    function savePracticeState(state) {
        if (!state) return;
        state.version = PRACTICE_VERSION;
        state.updatedAt = nowISO();
        if (state.lectureId === undefined || state.lectureId === null) {
            return;
        }
        var key = getPracticeKey(state.lectureId);
        localStorage.setItem(key, JSON.stringify(state));
    }

    function getAnswer(state, questionId) {
        if (!state || !state.answers) return null;
        return state.answers[String(questionId)] || null;
    }

    function setAnswer(lectureId, questionId, answer) {
        var state = loadPracticeState(lectureId);
        var key = String(questionId);
        if (!state.answers) {
            state.answers = {};
        }
        var normalized = normalizeAnswerEntry(key, answer, null, false);
        if (!normalized) {
            delete state.answers[key];
        } else {
            state.answers[key] = normalized;
        }
        savePracticeState(state);
    }

    function clearPracticeState(lectureId) {
        localStorage.removeItem(getPracticeKey(lectureId));
    }

    function loadPracticeResult(lectureId) {
        var key = getPracticeResultKey(lectureId);
        var raw = localStorage.getItem(key);
        if (!raw) return null;

        var parsed;
        try {
            parsed = JSON.parse(raw);
        } catch (e) {
            return null;
        }

        if (parsed && parsed.version === PRACTICE_VERSION && parsed.payload) {
            return parsed;
        }

        var wrapped = {
            version: PRACTICE_VERSION,
            lectureId: lectureId,
            submittedAt: nowISO(),
            payload: parsed
        };
        localStorage.setItem(key, JSON.stringify(wrapped));
        return wrapped;
    }

    function savePracticeResult(lectureId, payload) {
        var key = getPracticeResultKey(lectureId);
        var submittedAt = payload && payload.submittedAt ? payload.submittedAt : nowISO();
        var wrapped = {
            version: PRACTICE_VERSION,
            lectureId: lectureId,
            submittedAt: submittedAt,
            payload: payload
        };
        localStorage.setItem(key, JSON.stringify(wrapped));
    }

    function clearPracticeResult(lectureId) {
        localStorage.removeItem(getPracticeResultKey(lectureId));
    }

    function exportLegacyAnswers(state) {
        var legacy = {};
        if (!state || !state.answers) return legacy;
        Object.keys(state.answers).forEach(function (key) {
            var entry = state.answers[key];
            if (!entry || !entry.type) return;
            if (entry.type === 'mcq') {
                var value = Array.isArray(entry.value) ? entry.value : normalizeMcqValue(entry.value);
                if (value && value.length > 0) {
                    legacy[key] = value;
                }
                return;
            }
            if (entry.type === 'short') {
                var text = normalizeShortValue(entry.value);
                if (text) {
                    legacy[key] = text;
                }
            }
        });
        return legacy;
    }

    window.getPracticeKey = getPracticeKey;
    window.getPracticeResultKey = getPracticeResultKey;
    window.nowISO = nowISO;
    window.loadPracticeState = loadPracticeState;
    window.savePracticeState = savePracticeState;
    window.getAnswer = getAnswer;
    window.setAnswer = setAnswer;
    window.clearPracticeState = clearPracticeState;
    window.loadPracticeResult = loadPracticeResult;
    window.savePracticeResult = savePracticeResult;
    window.clearPracticeResult = clearPracticeResult;
    window.exportLegacyAnswers = exportLegacyAnswers;
})();
