function OriginalClipRestore({clip,onRestored,disabled}) {
  const [info,setInfo]=reactExports.useState(null);
  const [busy,setBusy]=reactExports.useState(false);
  const [error,setError]=reactExports.useState("");
  reactExports.useEffect(()=>{let gone=false;request$1(`/clips/${clip.id}/original-state`).then(v=>{if(!gone)setInfo(v);}).catch(e=>{if(!gone)setError(errorText(e));});return()=>{gone=true;};},[clip.id]);
  const restore=async()=>{setBusy(true);setError("");try{await request$1(`/clips/${clip.id}/restore-original`,{method:"POST"});onRestored();}catch(e){setError(errorText(e));}finally{setBusy(false);}};
  return jsxRuntimeExports.jsxs("section",{className:"rounded-lg border border-raised p-3 space-y-2","aria-label":"Откат клипа к оригиналу",children:[
    jsxRuntimeExports.jsx("h3",{className:"font-semibold text-sm",children:"Первоначальная версия клипа"}),
    jsxRuntimeExports.jsx("p",{className:"text-xs text-muted",children:info?.available?(info.kind==="created"?"Вернёт видео, границы, монтаж и субтитры к версии при создании клипа.":"Клип существовал до добавления отката. Точка возврата — версия, сохранённая при включении этой функции."):info?.reason||"Проверка сохранённого оригинала…"}),
    info?.available&&jsxRuntimeExports.jsx("p",{className:"text-xs text-muted",children:`Исходные границы: ${sourceTimeText(info.start)} → ${sourceTimeText(info.end)}. Текущие правки редактора будут сброшены.`}),
    jsxRuntimeExports.jsx("button",{type:"button",className:"btn-ghost",disabled:busy||disabled||!info?.available,onClick:()=>void restore(),children:busy?"Восстановление…":"↶ Откатить клип к первоначальной версии"}),
    error&&jsxRuntimeExports.jsx("p",{role:"alert",className:"text-sm text-error",children:error})
  ]});
}
