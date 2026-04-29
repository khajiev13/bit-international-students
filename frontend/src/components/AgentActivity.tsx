type AgentActivityProps = {
  hasResponse?: boolean;
  title: string;
  items: string[];
  locale?: "en" | "zh-CN";
  status?: "streaming" | "complete" | "error";
};

type ActivityPhase = "understand" | "explore" | "evidence" | "answer";

type ActivityGroup = {
  code: string;
  count: number;
  firstIndex: number;
  key: string;
  phase: ActivityPhase;
  subtitle: string;
  title: string;
};

const STAGE_ORDER: ActivityPhase[] = ["understand", "explore", "evidence", "answer"];

const COPY = {
  en: {
    actions: "actions",
    complete: "Complete",
    evidence: "evidence reads",
    groupSuffix: (count: number) => (count === 1 ? "time" : "times"),
    indexes: "index reads",
    progress: "Progress",
    running: "Running",
    statusError: "Needs attention",
    summary: "Agent used",
    stages: {
      answer: "Preparing answer",
      evidence: "Reading evidence",
      explore: "Exploring corpus",
      understand: "Understanding request"
    }
  },
  "zh-CN": {
    actions: "个动作",
    complete: "已完成",
    evidence: "次资料读取",
    groupSuffix: () => "次",
    indexes: "次索引读取",
    progress: "进度",
    running: "处理中",
    statusError: "需要检查",
    summary: "智能体使用了",
    stages: {
      answer: "整理回答",
      evidence: "读取证据",
      explore: "探索资料库",
      understand: "理解问题"
    }
  }
};

const ACTIVITY_META: Record<
  string,
  {
    code: string;
    label: (count: number, locale: keyof typeof COPY) => string;
    phase: ActivityPhase;
    subtitle: Record<keyof typeof COPY, string>;
  }
> = {
  "listing departments": {
    code: "D",
    label: (_count, locale) => (locale === "zh-CN" ? "查看可用院系" : "Checked available departments"),
    phase: "explore",
    subtitle: {
      en: "Finding schools that may match the student's topic.",
      "zh-CN": "先找到可能匹配学生问题的学院。"
    }
  },
  "reading a department index": {
    code: "I",
    label: (count, locale) =>
      locale === "zh-CN" ? `扫描了 ${count} 个院系索引` : `Scanned ${count} department ${count === 1 ? "index" : "indexes"}`,
    phase: "explore",
    subtitle: {
      en: "Reviewing department overviews before choosing profiles.",
      "zh-CN": "在选择教授资料前先查看院系概览。"
    }
  },
  "listing professor profiles": {
    code: "P",
    label: (_count, locale) => (locale === "zh-CN" ? "查看教授资料列表" : "Checked professor profile list"),
    phase: "explore",
    subtitle: {
      en: "Looking at the candidate pool available in the corpus.",
      "zh-CN": "查看资料库中的候选教授范围。"
    }
  },
  "searching professor profiles": {
    code: "S",
    label: (_count, locale) => (locale === "zh-CN" ? "搜索教授资料" : "Searched professor profiles"),
    phase: "explore",
    subtitle: {
      en: "Looking across names, research interests, and profile text.",
      "zh-CN": "从姓名、研究方向和资料正文中搜索线索。"
    }
  },
  "reading a professor profile": {
    code: "R",
    label: (count, locale) =>
      locale === "zh-CN" ? `读取了 ${count} 份教授资料` : `Read ${count} professor ${count === 1 ? "profile" : "profiles"}`,
    phase: "evidence",
    subtitle: {
      en: "Checking individual dossiers for evidence before answering.",
      "zh-CN": "回答前逐份检查教授资料中的证据。"
    }
  },
  "reviewing selected professor profiles": {
    code: "C",
    label: (_count, locale) => (locale === "zh-CN" ? "查看已选教授资料" : "Reviewed selected professor profiles"),
    phase: "evidence",
    subtitle: {
      en: "Checking selected profiles before writing the answer.",
      "zh-CN": "在回答前检查已选教授资料。"
    }
  },
  "updating the agent todo list": {
    code: "T",
    label: (_count, locale) => (locale === "zh-CN" ? "更新任务计划" : "Updated the work plan"),
    phase: "understand",
    subtitle: {
      en: "Organizing the agent's next steps.",
      "zh-CN": "整理智能体接下来的行动。"
    }
  },
  "writing a scratch file": {
    code: "W",
    label: (_count, locale) => (locale === "zh-CN" ? "记录临时笔记" : "Saved scratch notes"),
    phase: "evidence",
    subtitle: {
      en: "Keeping temporary notes separate from the read-only professor corpus.",
      "zh-CN": "把临时笔记与只读教授资料库分开保存。"
    }
  },
  "editing a scratch file": {
    code: "E",
    label: (_count, locale) => (locale === "zh-CN" ? "整理临时笔记" : "Refined scratch notes"),
    phase: "evidence",
    subtitle: {
      en: "Updating temporary notes before synthesis.",
      "zh-CN": "在综合回答前整理临时笔记。"
    }
  },
  "listing support files": {
    code: "F",
    label: (_count, locale) => (locale === "zh-CN" ? "查看辅助资料" : "Checked supporting files"),
    phase: "explore",
    subtitle: {
      en: "Looking for extra context that may help answer the question.",
      "zh-CN": "查找可能帮助回答问题的辅助资料。"
    }
  },
  "reading a support file": {
    code: "F",
    label: (_count, locale) => (locale === "zh-CN" ? "读取辅助资料" : "Read supporting material"),
    phase: "evidence",
    subtitle: {
      en: "Reviewing supporting context before answering.",
      "zh-CN": "回答前查看辅助上下文。"
    }
  },
  "finding support files": {
    code: "F",
    label: (_count, locale) => (locale === "zh-CN" ? "查找辅助资料" : "Found supporting material"),
    phase: "explore",
    subtitle: {
      en: "Finding material that may connect to the student's question.",
      "zh-CN": "查找可能与学生问题相关的资料。"
    }
  },
  "searching support files": {
    code: "F",
    label: (count, locale) =>
      locale === "zh-CN" ? `搜索了 ${count} 次辅助资料` : `Searched supporting material ${count} ${count === 1 ? "time" : "times"}`,
    phase: "explore",
    subtitle: {
      en: "Checking supporting text for matching professor evidence.",
      "zh-CN": "在辅助文本中查找匹配的导师证据。"
    }
  }
};

export function AgentActivity({
  hasResponse = false,
  title,
  items,
  locale = "en",
  status = "complete"
}: AgentActivityProps) {
  const copy = COPY[locale];
  const groups = groupActivities(items, locale);
  const progress = getProgress(groups, status, hasResponse);
  const stageStates = getStageStates(groups, status, hasResponse);
  const summary = buildSummary(items, copy);
  const statusLabel = status === "error" ? copy.statusError : status === "streaming" ? copy.running : copy.complete;

  return (
    <section className={`activity is-${status}`} aria-label={title}>
      <div className="activity-header">
        <span className="activity-count">{items.length}</span>
        <span className="activity-heading">
          <span>{title}</span>
          <small>{summary}</small>
        </span>
        <span className="activity-status">{statusLabel}</span>
      </div>
      <div className="activity-body">
        <div className="activity-progress" aria-label={copy.progress}>
          <div className="activity-progress-meta">
            <span>{copy.progress}</span>
            <b>{progress}%</b>
          </div>
          <div className="activity-progress-track" aria-hidden="true">
            <span style={{ width: `${progress}%` }} />
          </div>
        </div>

        <ol className="activity-stages" aria-label={copy.progress}>
          {STAGE_ORDER.map((stage) => (
            <li className={`activity-stage is-${stageStates[stage]}`} key={stage}>
              <span className="activity-stage-dot" aria-hidden="true" />
              <span>{copy.stages[stage]}</span>
            </li>
          ))}
        </ol>

        <ul className="activity-groups" aria-label={title}>
          {groups.map((group) => (
            <li className="activity-group" key={group.key} style={{ animationDelay: `${group.firstIndex * 45}ms` }}>
              <span className="activity-group-code" aria-hidden="true">
                {group.code}
              </span>
              <span className="activity-group-copy">
                <b>{group.title}</b>
                <small>{group.subtitle}</small>
              </span>
              <span className="activity-group-count">
                {group.count} {copy.groupSuffix(group.count)}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function groupActivities(items: string[], locale: keyof typeof COPY): ActivityGroup[] {
  const groups = new Map<string, ActivityGroup>();

  items.forEach((item, index) => {
    const key = item.trim().toLowerCase();
    const meta = ACTIVITY_META[key];
    const existing = groups.get(key);
    if (existing) {
      existing.count += 1;
      existing.title = meta ? meta.label(existing.count, locale) : item;
      return;
    }

    groups.set(key, {
      code: meta?.code || "A",
      count: 1,
      firstIndex: index,
      key: `${key}-${index}`,
      phase: meta?.phase || "explore",
      subtitle:
        meta?.subtitle[locale] ||
        (locale === "zh-CN" ? "记录一个安全的高层智能体动作。" : "Recorded one safe high-level agent action."),
      title: meta ? meta.label(1, locale) : item
    });
  });

  return [...groups.values()];
}

function buildSummary(items: string[], copy: (typeof COPY)[keyof typeof COPY]) {
  const indexReads = countMatches(items, "Reading a department index");
  const profileReads = countMatches(items, "Reading a professor profile");
  const parts: string[] = [];

  if (indexReads > 0) {
    parts.push(`${indexReads} ${copy.indexes}`);
  }
  if (profileReads > 0) {
    parts.push(`${profileReads} ${copy.evidence}`);
  }

  if (copy === COPY["zh-CN"]) {
    return parts.length
      ? `${copy.summary} ${items.length} ${copy.actions} · ${parts.join(" · ")}`
      : `${copy.summary} ${items.length} ${copy.actions}`;
  }

  return parts.length
    ? `${copy.summary} ${items.length} ${copy.actions} · ${parts.join(" · ")}`
    : `${copy.summary} ${items.length} ${copy.actions}`;
}

function countMatches(items: string[], match: string) {
  return items.filter((item) => item === match).length;
}

function getProgress(groups: ActivityGroup[], status: AgentActivityProps["status"], hasResponse: boolean) {
  if (status === "complete" || status === "error") {
    return 100;
  }
  const activeIndex = STAGE_ORDER.indexOf(getActivePhase(groups, hasResponse));
  return Math.max(25, Math.round(((activeIndex + 1) / STAGE_ORDER.length) * 100));
}

function getStageStates(
  groups: ActivityGroup[],
  status: AgentActivityProps["status"],
  hasResponse: boolean
): Record<ActivityPhase, "done" | "active" | "queued" | "error"> {
  if (status === "complete") {
    return { answer: "done", evidence: "done", explore: "done", understand: "done" };
  }
  if (status === "error") {
    return { answer: "error", evidence: "done", explore: "done", understand: "done" };
  }

  const activeIndex = STAGE_ORDER.indexOf(getActivePhase(groups, hasResponse));
  return STAGE_ORDER.reduce(
    (states, stage, index) => {
      states[stage] = index < activeIndex ? "done" : index === activeIndex ? "active" : "queued";
      return states;
    },
    {} as Record<ActivityPhase, "done" | "active" | "queued" | "error">
  );
}

function getActivePhase(groups: ActivityGroup[], hasResponse: boolean): ActivityPhase {
  if (hasResponse) {
    return "answer";
  }
  if (!groups.length) {
    return "understand";
  }
  return groups[groups.length - 1].phase;
}
