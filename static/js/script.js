(() => {
  const fieldNames = ["power", "main_switch", "fuse", "wiring", "bulb", "breaker", "overload", "connection"];

  function formPayload(form) {
    const data = new FormData(form);
    const result = {};
    for (const name of fieldNames) result[name] = data.get(name) || "unknown";
    result.symptoms = data.getAll("symptoms");
    if (data.has("query")) result.query = data.get("query");
    return result;
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.details ? body.details.join(" ") : body.error || "The request could not be completed.");
    return body;
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function section(title, content, className) {
    const block = element("div", `result-block ${className || ""}`);
    block.append(element("h3", "", title));
    block.append(content);
    return block;
  }

  function renderDiagnosis(result, target) {
    target.replaceChildren();
    target.classList.remove("hidden");
    const card = element("article", "panel diagnosis-output");
    const head = element("div", "result-header");
    const marker = element("span", `result-status ${result.consistent ? "status-ok" : "status-error"}`, result.consistent ? "∴" : "!");
    const titleWrap = element("div");
    titleWrap.append(element("div", "eyebrow", result.status.toUpperCase()));
    titleWrap.append(element("h2", "", result.summary));
    head.append(marker, titleWrap);
    card.append(head);

    if (!result.consistent) {
      const warning = element("div", "callout warning-callout");
      warning.append(element("span", "", "!"), element("p", "", "The observations are contradictory. No fault cause is presented as a valid conclusion."));
      card.append(warning);
    }

    const observationList = element("div", "fact-chips");
    for (const fact of result.observations) {
      const chip = element("span", "fact-chip");
      chip.append(element("b", "", `${fact.symbol} = ${fact.value ? "T" : "F"}`), document.createTextNode(fact.name));
      observationList.append(chip);
    }
    if (!result.observations.length) observationList.append(element("span", "muted-copy", "No facts were supplied."));
    card.append(section("Observed facts", observationList));

    const derivedList = element("div", "derived-list");
    for (const fact of result.derived) {
      const item = element("div", "derived-item");
      item.append(element("span", "derived-symbol", `${fact.symbol} = ${fact.value ? "T" : "F"}`));
      item.append(element("span", "", fact.name));
      item.append(element("span", "proof-tag", "PROVEN"));
      derivedList.append(item);
    }
    if (!result.derived.length) derivedList.append(element("p", "muted-copy", "No new literal conclusions were derived by forward chaining."));
    card.append(section("Proven conclusions", derivedList));

    const causeList = element("div", "cause-list");
    for (const cause of result.causes) {
      const item = element("article", `cause-item ${cause.certainty === "observed" ? "cause-confirmed" : ""}`);
      const badge = cause.certainty === "observed" ? "OBSERVED CONDITION" : "POSSIBLE — NOT PROVEN";
      item.append(element("div", "cause-item-top", badge));
      item.append(element("h4", "", cause.name));
      item.append(element("p", "", cause.explanation));
      item.append(element("code", "", `${cause.rule_id}: ${cause.rule}`));
      causeList.append(item);
    }
    if (!result.causes.length) causeList.append(element("p", "muted-copy", "No candidate causes can be reported from this evidence."));
    card.append(section("Possible explanations", causeList));

    const steps = element("ol", "reasoning-steps");
    for (const step of result.steps) {
      const item = element("li", `reasoning-step step-${step.kind}`);
      item.append(element("span", "step-marker", step.kind === "inference" ? "→" : step.kind === "observation" ? "•" : "∴"));
      const body = element("div");
      body.append(element("b", "", step.title));
      body.append(element("p", "", step.text));
      if (step.formula) body.append(element("code", "", `${step.formula}  ⟹  ${step.conclusion}`));
      item.append(body);
      steps.append(item);
    }
    card.append(section("Reasoning explanation", steps));
    const footer = element("div", "result-footnote", `Consistency: ${result.consistent ? "consistent" : "inconsistent"} · Satisfying models: ${result.models}`);
    card.append(footer);
    target.append(card);
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderEntailment(result, target) {
    target.replaceChildren();
    target.classList.remove("hidden");
    const card = element("article", `panel entail-output entail-${result.status.toLowerCase()}`);
    const top = element("div", "entail-result-top");
    top.append(element("span", `truth-badge truth-${result.status.toLowerCase()}`, result.status));
    const detail = element("div");
    detail.append(element("div", "eyebrow", `QUERY: ${result.query}`));
    detail.append(element("h3", "", result.explanation));
    top.append(detail);
    card.append(top);
    const facts = element("div", "fact-chips");
    for (const label of result.observations) facts.append(element("span", "fact-chip", label));
    if (!result.observations.length) facts.append(element("span", "muted-copy", "No observations supplied."));
    card.append(section("Evidence provided", facts));
    const modelsNote = element("p", "model-count", `The model checker evaluated ${result.models} satisfying model${result.models === 1 ? "" : "s"}.`);
    card.append(section("Model-checking result", modelsNote));
    if (result.backward_proof && result.backward_proof.proven) {
      const proofList = element("ol", "reasoning-steps");
      for (const step of result.backward_proof.steps) {
        const li = element("li", "reasoning-step step-inference");
        li.append(element("span", "step-marker", "→"));
        const body = element("div");
        body.append(element("b", "", `Rule ${step.rule_id}`));
        body.append(element("p", "", step.description));
        body.append(element("code", "", step.rule));
        li.append(body);
        proofList.append(li);
      }
      card.append(section("Backward-chain proof", proofList));
    }
    target.append(card);
    target.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  const diagnosisForm = document.querySelector("#diagnosis-form");
  if (diagnosisForm) {
    diagnosisForm.addEventListener("submit", async event => {
      event.preventDefault();
      const button = diagnosisForm.querySelector('button[type="submit"]');
      button.disabled = true;
      button.textContent = "Reasoning…";
      try {
        renderDiagnosis(await postJson("/api/diagnose", formPayload(diagnosisForm)), document.querySelector("#diagnosis-result"));
      } catch (error) {
        showError(document.querySelector("#diagnosis-result"), error.message);
      } finally {
        button.disabled = false;
        button.textContent = "∴ Diagnose fault";
      }
    });
  }

  document.querySelectorAll("[data-scenario]").forEach(button => {
    button.addEventListener("click", async () => {
      const resultTarget = document.querySelector("#scenario-result");
      document.querySelectorAll("[data-scenario]").forEach(item => item.classList.remove("scenario-selected"));
      button.classList.add("scenario-selected");
      button.disabled = true;
      try {
        const result = await postJson(`/api/scenario/${button.dataset.scenario}`, {});
        renderDiagnosis(result, resultTarget);
      } catch (error) {
        showError(resultTarget, error.message);
      } finally {
        button.disabled = false;
      }
    });
  });

  const entailmentForm = document.querySelector("#entailment-form");
  if (entailmentForm) {
    entailmentForm.addEventListener("submit", async event => {
      event.preventDefault();
      const button = entailmentForm.querySelector('button[type="submit"]');
      button.disabled = true;
      button.textContent = "Checking models…";
      try {
        renderEntailment(await postJson("/api/entailment", formPayload(entailmentForm)), document.querySelector("#entailment-result"));
      } catch (error) {
        showError(document.querySelector("#entailment-result"), error.message);
      } finally {
        button.disabled = false;
        button.textContent = "Check entailment →";
      }
    });
  }

  function showError(target, message) {
    target.replaceChildren();
    target.classList.remove("hidden");
    const card = element("div", "callout warning-callout");
    card.append(element("span", "", "!"), element("p", "", message));
    target.append(card);
  }
})();
