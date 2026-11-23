function VideoMontageChoice({ options, onChange }) {
  const [saved, setSaved] = reactExports.useState([]);
  const [loading, setLoading] = reactExports.useState(true);
  const [error, setError] = reactExports.useState("");
  const [count, setCount] = reactExports.useState(String(options.montage?.clip_limit ?? 1));
  const [limited, setLimited] = reactExports.useState(!!options.montage?.clip_limit);
  const current = reactExports.useRef(options);
  current.current = options;
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await montageApi.templates();
      setSaved(data.templates);
      if (current.current.montage === undefined) {
        const preset = data.templates.find((item) => item.id === data.default_id);
        onChange(preset ? { montage: { ...preset.settings }, montage_template_id: preset.id } : { montage: false, montage_template_id: "" });
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  };
  reactExports.useEffect(() => { void load(); }, []);
  const selectedId = options.montage_template_id ?? "";
  const enabled = !!options.montage && typeof options.montage === "object";
  const choose = (id) => {
    const preset = saved.find((item) => item.id === id);
    setLimited(false);
    setCount("1");
    onChange(preset ? { montage: { ...preset.settings }, montage_template_id: id } : { montage: false, montage_template_id: "" });
  };
  const applyLimit = (value) => {
    const next = { ...options.montage };
    if (value === null) delete next.clip_limit;
    else next.clip_limit = value;
    onChange({ montage: next });
  };
  const field = (text, child) => jsxRuntimeExports.jsxs("label", { className: "space-y-1 text-sm", children: [jsxRuntimeExports.jsx("span", { className: "block label", children: text }), child] });
  return jsxRuntimeExports.jsxs("section", { className: "space-y-2 border-t border-raised/60 pt-3 mt-3", "aria-label": "Шаблон монтажа для видео", children: [
    jsxRuntimeExports.jsxs("div", { className: "flex items-end gap-3 flex-wrap", children: [
      field("Шаблон монтажа", jsxRuntimeExports.jsxs("select", { className: "input !w-80 max-w-full", value: selectedId, disabled: loading, onChange: (e) => choose(e.target.value), children: [
        jsxRuntimeExports.jsx("option", { value: "", children: loading ? "Загрузка шаблонов…" : "Без шаблона" }),
        enabled && selectedId && !saved.some((item) => item.id === selectedId) && jsxRuntimeExports.jsx("option", { value: selectedId, children: options.montage.name + " (сохранён в задании)" }),
        saved.map((item) => jsxRuntimeExports.jsx("option", { value: item.id, children: item.settings.name }, item.id))
      ] })),
      jsxRuntimeExports.jsx("button", { type: "button", className: "btn-ghost !py-2", disabled: loading, onClick: () => void load(), children: "Обновить шаблоны" }),
      enabled && field("Применить шаблон", jsxRuntimeExports.jsxs("select", { className: "input !w-64", value: limited ? "count" : "all", onChange: (e) => { const on = e.target.value === "count"; setLimited(on); applyLimit(on ? Number(count) || 1 : null); }, children: [
        jsxRuntimeExports.jsx("option", { value: "all", children: "Ко всем клипам" }),
        jsxRuntimeExports.jsx("option", { value: "count", children: "К первым N клипам по рейтингу" })
      ] })),
      enabled && limited && field("Количество клипов", jsxRuntimeExports.jsx("input", { type: "number", min: 1, step: 1, className: "input !w-28", value: count, onChange: (e) => { const value = e.target.value; setCount(value); const n = Number(value); if (Number.isInteger(n) && n > 0) applyLimit(n); }, onBlur: () => { const n = Number(count); if (!Number.isInteger(n) || n < 1) { setCount("1"); applyLimit(1); } } }))
    ] }),
    enabled && jsxRuntimeExports.jsxs("p", { className: "text-xs text-muted", children: [
      "После нарезки автоматически добавятся реклама, второе видео и музыка из шаблона. ",
      limited ? "Выбираются клипы с наибольшим рейтингом; остальные останутся без шаблона. " : "",
      "Готовые версии: ", options.montage.folder || "папка exports в данных приложения", ". Управление шаблонами — в разделе «Шаблоны монтажа»."
    ] }),
    error && jsxRuntimeExports.jsx("p", { role: "alert", className: "text-sm text-error", children: error }),
    !loading && !saved.length && !error && jsxRuntimeExports.jsx("p", { className: "text-xs text-muted", children: "Сначала создайте и сохраните шаблон в разделе «Шаблоны монтажа»." })
  ] });
}
