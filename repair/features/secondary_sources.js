function SecondaryVideoSources({ options, patch, perform }) {
  const files = options.files ?? [];
  const addFiles = () => perform(async () => {
    const selected = await window.studio.pickVideoFiles();
    if (selected?.length) {
      patch(current => ({ enabled: true, files: [...new Set([...(current.files ?? []), ...selected])] }));
    }
  });
  return jsxRuntimeExports.jsxs("div", { className: "space-y-2", children: [
    jsxRuntimeExports.jsx(Check, {
      label: "Генерировать видео с шариком и кольцами",
      value: options.bouncing_ball ?? false,
      onChange: bouncing_ball => patch(bouncing_ball ? { bouncing_ball, enabled: true } : { bouncing_ball })
    }),
    jsxRuntimeExports.jsx("button", {
      type: "button", className: "btn-ghost", onClick: addFiles, children: "Добавить видеофайлы…"
    }),
    files.length > 0 && jsxRuntimeExports.jsx("ul", {
      className: "space-y-1",
      children: files.map((path, index) => jsxRuntimeExports.jsxs("li", {
        className: "flex items-center gap-2 text-sm",
        children: [
          jsxRuntimeExports.jsx("span", {
            className: "flex-1 min-w-0 truncate", title: path,
            children: `${index + 1}. ${path.split(/[\\/]/).pop()}`
          }),
          jsxRuntimeExports.jsx("button", {
            type: "button", className: "btn-ghost text-xs", title: path,
            onClick: () => patch(current => ({ files: current.files.filter(file => file !== path) })),
            children: "Убрать"
          })
        ]
      }, path))
    }),
    (files.length > 0 || options.bouncing_ball) && jsxRuntimeExports.jsx("p", {
      className: "text-xs text-muted",
      children: `Доп. видео на клип: ${files.length + Number(!!options.bouncing_ball)}. Каждый источник — отдельная версия экспорта.`
    })
  ] });
}
