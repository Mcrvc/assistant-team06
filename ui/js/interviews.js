/* The team's UI shape <-> canonical interview API. Writes run in page order. */
(() => {
  "use strict";
  let queue = Promise.resolve();
  const submittedHere = new Set();
  const enqueue = task => {
    const next = queue.catch(() => {}).then(task);
    queue = next;
    return next;
  };
  function checked(response) {
    if (!response?.ok) {
      const error = new Error(response?.data?.error?.message || "Could not reach the server. Your draft is kept on this device.");
      error.code = response?.data?.error?.code;
      throw error;
    }
    return response.data;
  }
  function updateVersion(item, data) {
    item.serverRevision = data.revision;
    item.serverAnswers = data.answers;
    item.serverCurrentQuestion = data.current_question;
    item.progress = data.progress;
    item.report = data.report;
  }
  function hasUnsavedChanges(item) {
    return item.answers.some((text, index) => text !== item.serverAnswers?.[index]?.text);
  }
  function discard(item) {
    item.answers = item.serverAnswers.map(answer => answer.text);
    item.currentQuestion = item.serverCurrentQuestion || 0;
    item.dirty = false;
  }
  function apply(item, data) {
    Object.assign(item, {
      id: data.id, backend: true, name: data.name,
      date: new Date(data.created_at).toLocaleDateString("en-GB"),
      answers: data.answers.map(answer => answer.text),
      questions: data.questions.map(question => question.text),
      currentQuestion: data.current_question, finished: data.status === "finalized", dirty: false,
    });
    updateVersion(item, data);
    return item;
  }
  async function create(item) {
    const config = await window.YourinConfigPromise;
    if (item.cvMode === "pdf" || item.cvPdf) {
      throw new Error("PDF interviews are not connected yet. Use CV text or continue without a CV.");
    }
    const cv = (item.cv || []).filter(Boolean).join("\n\n");
    if (cv && !config.interviewCvEnabled) {
      throw new Error("CV sharing is disabled for this server. Continue without a CV for now.");
    }
    const job = item.job || {};
    if (!job["job-title"] && /^https?:\/\/\S+$/.test((job["job-source"] || "").trim())) {
      throw new Error("Job links are not imported yet. Paste the job description text or enter the role fields.");
    }
    const created = checked(await window.YourinAPI.createInterview({
      name: item.name,
      job_profile: { title: job["job-title"] || "", description: job["job-source"] || "",
        domain: job.domain || "", company: job.company || "", level: job.position || "" },
      cv: cv || null,
    }));
    item.id = created.id;
    item.backend = true;
    return restore(item);
  }
  async function restore(item) {
    return apply(item, checked(await window.YourinAPI.getInterview(item.id)));
  }
  function save(item, currentQuestion, status = "in_progress", includeAnswers = true) {
    const answers = [...item.answers];
    return enqueue(async () => {
      const data = checked(await window.YourinAPI.saveProgress(item.id, {
        revision: item.serverRevision, ...(includeAnswers ? { answers } : {}),
        current_question: currentQuestion, status,
      }));
      updateVersion(item, data);
      item.currentQuestion = currentQuestion;
      item.dirty = hasUnsavedChanges(item);
      return data;
    });
  }
  function submit(item, index, force = false) {
    const text = item.answers[index];
    return enqueue(async () => {
      if (!text?.trim()) throw new Error("Please answer this question before continuing.");
      const known = item.serverAnswers?.[index];
      const key = JSON.stringify([item.id, index, text]);
      if (!force && known?.text === text && (known.grading_status === "graded"
          || (known.grading_status === "pending" && submittedHere.has(key)))) {
        item.dirty = hasUnsavedChanges(item);
        return;
      }
      const data = checked(await window.YourinAPI.submitAnswer(item.id, index, {
        revision: item.serverRevision, text,
      }));
      updateVersion(item, data);
      submittedHere.add(key);
      item.dirty = hasUnsavedChanges(item);
    });
  }
  async function retryPending(item) {
    await restore(item);
    for (let index = 0; index < 3; index++) {
      if (item.serverAnswers[index].grading_status !== "graded" && item.answers[index].trim()) {
        await submit(item, index, true);
      }
    }
  }
  async function finalize(item, name, onProgress = () => {}) {
    await queue.catch(() => {});
    const deadline = Date.now() + 90000;
    while (true) {
      const counts = checked(await window.YourinAPI.getProgress(item.id));
      onProgress(counts);
      if (counts.graded === 3) break;
      if (counts.rejected) throw new Error("An AI quotation could not be verified. Return to the interview and re-submit that answer.");
      if (counts.answered < 3) throw new Error("All three answers are required. Return to the interview to complete them.");
      if (!counts.pending || Date.now() > deadline) {
        throw new Error("Grading is incomplete. Return to the interview and re-submit pending or draft answers to retry.");
      }
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    const data = checked(await window.YourinAPI.finalizeInterview(item.id, {
      revision: item.serverRevision, ...(name ? { name } : {}),
    }));
    return apply(item, data);
  }
  window.YourinInterviews = { create, restore, save, submit, finalize, retryPending, hasUnsavedChanges, discard };
})();
