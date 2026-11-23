function ExistingClipTemplates({ clipIds, shownIds, onSelect, videoId }) {
  const [templates, setTemplates] = reactExports.useState([]);
  const [templateId, setTemplateId] = reactExports.useState("");
  const [busy, setBusy] = reactExports.useState(false);
  const [error, setError] = reactExports.useState("");
  const [jobId, setJobId] = reactExports.useState(null);
  const [job, setJob] = reactExports.useState(null);
  const [folder, setFolder] = reactExports.useState("");
  const load = async () => {
    try {
      const data = await montageApi.templates();
      setTemplates(data.templates);
      setTemplateId((old) => data.templates.some((item) => item.id === old) ? old : data.default_id || data.templates[0]?.id || "");
      setError("");
    } catch (e) { setError(errorText(e)); }
  };
  reactExports.useEffect(() => { void load(); }, []);
  reactExports.useEffect(() => {
    if (!jobId) return;
    let disposed = false, timer;
    const poll = async () => {
      try {
        const next = await montageApi.job(jobId);
        if (disposed) return;
        setJob(next);
        if (next.status === "queued" || next.status === "running") timer = setTimeout(poll, 1000);
      } catch (e) {
        if (!disposed) { setError(errorText(e)); timer = setTimeout(poll, 3000); }
      }
    };
    void poll();
    return () => { disposed = true; clearTimeout(timer); };
  }, [jobId]);
  const active = jobId && (!job || job.status === "queued" || job.status === "running");
  const preset = templates.find((item) => item.id === templateId);
  const run = async () => {
    setBusy(true); setError("");
    try {
      if (!preset) throw new Error("Выберите сохранённый шаблон");
      const exportFolder = folder.trim() || preset.settings.folder;
      if (!exportFolder) throw new Error("Укажите папку для готовых версий");
      const result = await montageApi.export([...clipIds], exportFolder, preset.settings);
      setJob(null); setJobId(result.job_id);
      await api.resumeQueue();
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  };
  return jsxRuntimeExports.jsxs("section", { className: "card space-y-3", "aria-label": "Шаблон для выбранных оригиналов", children: [
    jsxRuntimeExports.jsx("h3", { className: "font-semibold", children: "Применить шаблон к готовым клипам" }),
    jsxRuntimeExports.jsxs("div", { className: "flex flex-wrap items-center gap-2", children: [
      jsxRuntimeExports.jsx("span", { className: "text-sm", children: `Выбрано оригиналов: ${clipIds.length}` }),
      jsxRuntimeExports.jsx("button", { type: "button", className: "btn-ghost !py-1 text-xs", disabled: !shownIds.length, onClick: () => onSelect([...shownIds]), children: "Выбрать все показанные" }),
      jsxRuntimeExports.jsx("button", { type: "button", className: "btn-ghost !py-1 text-xs", disabled: !clipIds.length, onClick: () => onSelect([]), children: "Снять выделение" })
    ] }),
    jsxRuntimeExports.jsxs("label", { className: "block text-sm space-y-1", children: [
      jsxRuntimeExports.jsx("span", { children: "Сохранённый шаблон" }),
      jsxRuntimeExports.jsxs("select", { className: "input w-full", value: templateId, disabled: busy || active, onChange: (e) => setTemplateId(e.target.value), children: [
        jsxRuntimeExports.jsx("option", { value: "", children: "Выберите шаблон" }),
        templates.map((item) => jsxRuntimeExports.jsx("option", { value: item.id, children: item.settings.name }, item.id))
      ] })
    ] }),
    jsxRuntimeExports.jsxs("label", { className: "block text-sm space-y-1", children: [
      jsxRuntimeExports.jsx("span", { children: "Папка результата (можно изменить)" }),
      jsxRuntimeExports.jsx("input", { className: "input w-full", value: folder, placeholder: preset?.settings.folder || "Укажите папку экспорта", onChange: (e) => setFolder(e.target.value), disabled: busy || active })
    ] }),
    jsxRuntimeExports.jsxs("div", { className: "flex flex-wrap gap-2", children: [
      jsxRuntimeExports.jsx("button", { type: "button", className: "btn-accent", disabled: busy || active || !clipIds.length || !preset, onClick: () => void run(), children: busy ? "Запуск…" : active ? "Применяется шаблон…" : `Применить шаблон (${clipIds.length})` }),
      jsxRuntimeExports.jsx("button", { type: "button", className: "btn-ghost", disabled: busy || active, onClick: () => void load(), children: "Обновить шаблоны" })
    ] }),
    jsxRuntimeExports.jsx("p", { className: "text-xs text-muted", children: "Создаются отдельные версии с рекламой, дополнительным видео и музыкой. Оригинальные клипы сохраняются без изменений." }),
    error && jsxRuntimeExports.jsx("p", { role: "alert", className: "text-sm text-error", children: error }),
    job && jsxRuntimeExports.jsxs("div", { className: "text-sm space-y-1", "aria-live": "polite", children: [
      jsxRuntimeExports.jsx("p", { children: `Задание ${job.id}: ${job.status}${job.progress ? ` · ${job.progress.percent}%` : ""}` }),
      job.error && jsxRuntimeExports.jsx("p", { className: "text-error", children: job.error }),
      job.montage_result?.folder && jsxRuntimeExports.jsx("p", { className: "break-all", children: `Папка результата: ${job.montage_result.folder}` }),
      job.montage_result?.files?.map((file) => jsxRuntimeExports.jsx("p", { className: "text-xs break-all", children: file }, file))
    ] })
  ] });
}
