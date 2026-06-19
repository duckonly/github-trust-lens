const form = document.querySelector("#analysisForm");
const statusPill = document.querySelector("#statusPill");
const submitButton = document.querySelector("#submitButton");
const resultArea = document.querySelector("#resultArea");
const emptyState = document.querySelector("#emptyState");
const scoreRing = document.querySelector("#scoreRing");
const scoreValue = document.querySelector("#scoreValue");
const gradeValue = document.querySelector("#gradeValue");
const repoName = document.querySelector("#repoName");
const repoDescription = document.querySelector("#repoDescription");
const checksList = document.querySelector("#checksList");
const exportJsonButton = document.querySelector("#exportJsonButton");

let latestReport = null;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(true);

  const data = Object.fromEntries(new FormData(form).entries());

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Analysis failed.");
    }
    renderReport(payload);
    setStatus("Complete", "success");
  } catch (error) {
    renderError(error.message);
    const isRateLimit = error.message.toLowerCase().includes("rate limit");
    setStatus(isRateLimit ? "API Limit" : "Error", "error");
  } finally {
    setBusy(false);
  }
});

exportJsonButton.addEventListener("click", () => {
  if (!latestReport) {
    return;
  }
  const repo = latestReport.repository.replace(/[^a-z0-9_-]+/gi, "-").replace(/^-|-$/g, "");
  const blob = new Blob([`${JSON.stringify(latestReport, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${repo || "trust-lens"}-report.json`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
});

function setBusy(isBusy) {
  submitButton.disabled = isBusy;
  submitButton.querySelector("span").textContent = isBusy ? "Analyzing" : "Analyze";
  if (isBusy) {
    setStatus("Running", "running");
  }
}

function setStatus(text, state = "idle") {
  statusPill.textContent = text;
  statusPill.dataset.state = state;
}

function renderReport(report) {
  latestReport = report;
  emptyState.hidden = true;
  resultArea.hidden = false;

  scoreValue.textContent = Math.round(report.score);
  gradeValue.textContent = report.grade;
  repoName.textContent = report.repository;
  repoDescription.textContent = report.description || "No repository description.";
  scoreRing.style.borderColor = colorForScore(report.score);

  checksList.replaceChildren(...report.checks.map(renderCheck));
}

function renderCheck(check) {
  const item = document.createElement("article");
  item.className = "check";

  const head = document.createElement("div");
  head.className = "check-head";

  const title = document.createElement("h3");
  title.className = "check-title";
  title.textContent = check.title;

  const score = document.createElement("div");
  score.className = `check-score ${scoreClass(check.score)}`;
  score.textContent = `${Math.round(check.score)}/100`;

  const summary = document.createElement("p");
  summary.className = "check-summary";
  summary.textContent = check.summary;

  const details = document.createElement("details");
  details.className = "check-details";

  const detailsTitle = document.createElement("summary");
  detailsTitle.textContent = "Score reasoning";

  const detailBody = document.createElement("div");
  detailBody.className = "detail-body";

  const basis = document.createElement("p");
  basis.textContent = managementReason(check);

  const risk = document.createElement("p");
  risk.className = "risk-note";
  risk.textContent = managementRisk(check);

  detailBody.append(basis, risk);
  details.append(detailsTitle, detailBody);

  head.append(title, score);
  item.append(head, summary, details);
  return item;
}

function renderError(message) {
  resultArea.hidden = true;
  emptyState.hidden = false;
  latestReport = null;
  emptyState.innerHTML = "";

  const heading = document.createElement("h2");
  heading.textContent = "Analysis failed";

  const body = document.createElement("p");
  body.textContent = message;

  emptyState.append(heading, body);
}

function managementReason(check) {
  const evidence = check.evidence || {};
  const score = Math.round(check.score);

  switch (check.id) {
    case "maintainer_discoverability":
      if (evidence.found?.length) {
        return `The score is ${score}/100 because ownership is documented through ${evidence.found.join(", ")}. This improves escalation paths, accountability, and auditability.`;
      }
      return `The score is ${score}/100 because no clear ownership files were found. For management, this makes it harder to identify who is accountable during an incident or exception review.`;

    case "governance_surface":
      if (evidence.found?.length) {
        return `The score is ${score}/100 because governance or participation documents such as ${evidence.found.join(", ")} are present. This indicates more predictable collaboration and project processes.`;
      }
      return `The score is ${score}/100 because no non-security governance documents were found. This makes the project appear less transparent and harder to govern.`;

    case "inferred_maintainer_roles": {
      const counts = evidence.role_counts || {};
      const strong = (counts.declared_maintainer || 0) + (counts.active_maintainer || 0);
      const probable = counts.probable_maintainer || 0;
      return `The score is ${score}/100 because ${strong} declared or active maintainers and ${probable} probable maintainers can be inferred from files and activity. Fewer visible roles mean weaker governance evidence.`;
    }

    case "maintainer_bus_factor":
      if (typeof evidence.top_ratio === "number") {
        return `The score is ${score}/100 because ${Math.round(evidence.top_ratio * 100)}% of recently merged PRs are concentrated under the leading merger account. High concentration indicates dependency on a small number of people.`;
      }
      return `The score is ${score}/100 because there is not enough merge data available. Without this data, personnel dependency can only be assessed with limited confidence.`;

    case "maintainer_account_maturity":
      if (typeof evidence.median_account_age_years === "number") {
        return `The score is ${score}/100 because the inferred maintainer accounts have a median age of ${evidence.median_account_age_years} years. Established account history improves confidence, while very new or thin accounts would lower it.`;
      }
      return `The score is ${score}/100 because no reliable maintainer profiles were available for this assessment. This leaves part of the identity and maturity review unresolved.`;

    case "maintainer_transparency":
      return `The score is ${score}/100 because the public profiles of inferred maintainers provide varying levels of context such as name, organization, location, or bio. Limited profile transparency makes accountability and reputation harder to assess.`;

    case "issue_handling_transparency":
    case "issue_response_quality":
      if (typeof evidence.explained_closure_ratio === "number") {
        const explained = Math.round(evidence.explained_closure_ratio * 100);
        const maintainerTouch = percentOrUnknown(evidence.maintainer_touch_ratio);
        const referencedWork = percentOrUnknown(evidence.referenced_work_ratio);
        const discussion = percentOrUnknown(evidence.discussion_ratio);
        const silent = percentOrUnknown(evidence.silent_closure_ratio);
        const closeTime = evidence.median_days_to_close ?? "unknown";
        return `The score is ${score}/100 because ${explained}% of recently closed issues had an explainable closure signal. The underlying signals are: maintainer touch ${maintainerTouch}, linked work ${referencedWork}, visible discussion ${discussion}, silent unexplained closures ${silent}, and median time to close ${closeTime} days. A high discussion rate alone does not create a high score if maintainer handling or linked remediation is missing.`;
      }
      if (typeof evidence.comment_ratio === "number" || typeof evidence.discussion_ratio === "number") {
        const ratio = evidence.comment_ratio ?? evidence.discussion_ratio;
        return `The score is ${score}/100 because ${Math.round(ratio * 100)}% of recently closed issues had visible discussion. Discussion alone is only a weak signal unless it also shows maintainer handling or a clear closure reason.`;
      }
      return `The score is ${score}/100 because there were not enough recently closed issues to assess handling transparency. Issue handling therefore remains uncertain.`;

    case "release_note_quality":
      if (typeof evidence.meaningful_release_note_ratio === "number") {
        return `The score is ${score}/100 because ${Math.round(evidence.meaningful_release_note_ratio * 100)}% of reviewed releases contain meaningful release notes. Weak release notes reduce traceability for change and risk decisions.`;
      }
      return `The score is ${score}/100 because no GitHub releases with assessable release notes were available. This makes changes harder to understand for management and security review.`;

    case "suspicious_maintainer_churn":
      if (typeof evidence.new_dominance === "number") {
        return `The score is ${score}/100 because the leading new merger accounts for ${Math.round(evidence.new_dominance * 100)}% of the newest merge sample. Sudden dominance by a new actor can indicate governance or handover risk.`;
      }
      return `The score is ${score}/100 because there is not enough merge history to assess maintainer churn reliably. Churn risk remains only partially visible.`;

    default:
      return `The score is ${score}/100. ${check.summary}`;
  }
}

function percentOrUnknown(value) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "unknown";
}

function managementRisk(check) {
  const riskByCheck = {
    maintainer_discoverability: "Risk: unclear ownership can delay incident communication, escalation, and exception approvals.",
    governance_surface: "Risk: missing governance increases the likelihood of inconsistent decisions and weak project steering.",
    inferred_maintainer_roles: "Risk: if roles are only weakly inferable, it remains unclear who actually controls the repository.",
    maintainer_bus_factor: "Risk: high concentration around a few people can threaten availability, review quality, and continuity.",
    maintainer_account_maturity: "Risk: young or thinly established accounts increase identity, reputation, and takeover concerns.",
    maintainer_transparency: "Risk: limited profile transparency makes due diligence and external accountability harder.",
    issue_response_quality: "Risk: weak issue response can indicate delayed remediation and limited operational care.",
    issue_handling_transparency: "Risk: opaque issue closure makes remediation decisions harder to audit and can hide weak triage or unresolved user impact.",
    release_note_quality: "Risk: unclear releases make change management, impact analysis, and security approvals harder.",
    suspicious_maintainer_churn: "Risk: unusual maintainer turnover can indicate handover issues or compromised governance.",
  };
  return riskByCheck[check.id] || "Risk: this finding should be assessed in the context of additional repository and organizational signals.";
}

function scoreClass(score) {
  if (score >= 70) {
    return "is-good";
  }
  if (score >= 45) {
    return "is-warn";
  }
  return "is-bad";
}

function colorForScore(score) {
  if (score >= 70) {
    return "#1c7c54";
  }
  if (score >= 45) {
    return "#b86b00";
  }
  return "#b83232";
}
