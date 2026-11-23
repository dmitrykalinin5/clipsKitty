function sourceTime(value) {
  const parts=String(value).trim().replace(",", ".").split(":");
  if (!parts.length || parts.length>3 || parts.some(p=>!/^\d+(?:\.\d+)?$/.test(p))) return NaN;
  return parts.reduce((sum,p)=>sum*60+Number(p),0);
}
function sourceTimeText(value) {
  if (!Number.isFinite(value)) return "";
  const t=Math.round(value*100)/100;
  const h=Math.floor(t/3600),m=Math.floor(t%3600/60),s=(t%60).toFixed(2).padStart(5,"0");
  return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:${s}`;
}
function SourceRangeEditor({clip,onChanged,disabled}) {
  const [info,setInfo]=reactExports.useState(null);
  const [start,setStart]=reactExports.useState(sourceTimeText(clip.start_s));
  const [end,setEnd]=reactExports.useState(sourceTimeText(clip.end_s));
  const [before,setBefore]=reactExports.useState("5");
  const [after,setAfter]=reactExports.useState("5");
  const [error,setError]=reactExports.useState("");
  const [jobId,setJobId]=reactExports.useState(null);
  const [job,setJob]=reactExports.useState(null);
  const [busy,setBusy]=reactExports.useState(false);
  const load=async()=>{
    try {setInfo(await request$1(`/clips/${clip.id}/source-range`));setError("");}
    catch(e){setError(errorText(e));}
  };
  reactExports.useEffect(()=>{setStart(sourceTimeText(clip.start_s));setEnd(sourceTimeText(clip.end_s));setInfo(null);void load();},[clip.id,clip.start_s,clip.end_s]);
  reactExports.useEffect(()=>{
    if(!jobId)return;
    let gone=false,timer;
    const poll=async()=>{
      try {
        const next=await request$1(`/jobs/${jobId}`);if(gone)return;setJob(next);
        if(next.status==="queued"||next.status==="running")timer=setTimeout(poll,1000);
        else if(next.status==="done"){onChanged();}
        else setError(next.error||`Задание: ${next.status}`);
      }catch(e){if(!gone){setError(errorText(e));timer=setTimeout(poll,3000);}}
    };
    void poll();return()=>{gone=true;clearTimeout(timer);};
  },[jobId]);
  const a=sourceTime(start),b=sourceTime(end);
  const valid=info&&Number.isFinite(a)&&Number.isFinite(b)&&a>=0&&b>a&&b<=info.source_duration+0.001;
  const active=jobId&&(!job||job.status==="queued"||job.status==="running");
  const locked=busy||active||disabled;
  const adjust=(side,seconds)=>{
    if(!info)return;
    const amount=sourceTime(seconds);
    if(!Number.isFinite(amount)||amount<=0){setError("Введите положительное число секунд, например 12.5");return;}
    if(side==="before")setStart(sourceTimeText(Math.max(0,(Number.isFinite(a)?a:clip.start_s)-amount)));
    else setEnd(sourceTimeText(Math.min(info.source_duration,(Number.isFinite(b)?b:clip.end_s)+amount)));
    setError("");
  };
  const apply=async()=>{
    if(!valid)return;setBusy(true);setError("");
    try {
      const result=await request$1(`/clips/${clip.id}/source-range`,{method:"POST",body:JSON.stringify({start:a,end:b})});
      setJob(null);setJobId(result.job_id);await api.resumeQueue();
    }catch(e){setError(errorText(e));}finally{setBusy(false);}
  };
  const input=(label,value,change,type="text")=>jsxRuntimeExports.jsxs("label",{className:"block text-sm space-y-1",children:[jsxRuntimeExports.jsx("span",{children:label}),jsxRuntimeExports.jsx("input",{className:"input w-full",type,value,disabled:locked,onChange:e=>change(e.target.value),...(type==="number"?{min:0,step:"any"}:{})})]});
  return jsxRuntimeExports.jsxs("section",{className:"rounded-lg border border-raised p-3 space-y-3", "aria-label":"Расширить клип из исходного видео",children:[
    jsxRuntimeExports.jsx("h3",{className:"font-semibold text-sm",children:"Расширить фрагмент из оригинала"}),
    jsxRuntimeExports.jsx("p",{className:"text-xs text-muted",children:info?`Исходник: ${sourceTimeText(info.source_duration)}. Можно добавлять любое число секунд в пределах исходника.`:"Проверка исходного видео…"}),
    jsxRuntimeExports.jsxs("div",{className:"grid grid-cols-1 sm:grid-cols-2 gap-3",children:[
      jsxRuntimeExports.jsxs("div",{className:"space-y-2",children:[input("Начало в исходнике (чч:мм:сс или секунды)",start,setStart),input("Добавить секунд до начала",before,setBefore,"number"),jsxRuntimeExports.jsxs("div",{className:"flex flex-wrap gap-2",children:[jsxRuntimeExports.jsx("button",{type:"button",className:"btn-ghost text-xs",disabled:locked||!info,onClick:()=>adjust("before",before),children:"← Добавить до начала"}),...[5,30,60].map(n=>jsxRuntimeExports.jsx("button",{type:"button",className:"btn-ghost text-xs !px-2",disabled:locked||!info,onClick:()=>adjust("before",String(n)),children:`−${n} с`},n))]})]}),
      jsxRuntimeExports.jsxs("div",{className:"space-y-2",children:[input("Конец в исходнике (чч:мм:сс или секунды)",end,setEnd),input("Добавить секунд после конца",after,setAfter,"number"),jsxRuntimeExports.jsxs("div",{className:"flex flex-wrap gap-2",children:[jsxRuntimeExports.jsx("button",{type:"button",className:"btn-ghost text-xs",disabled:locked||!info,onClick:()=>adjust("after",after),children:"Добавить после конца →"}),...[5,30,60].map(n=>jsxRuntimeExports.jsx("button",{type:"button",className:"btn-ghost text-xs !px-2",disabled:locked||!info,onClick:()=>adjust("after",String(n)),children:`+${n} с`},n))]})]})
    ]}),
    info&&jsxRuntimeExports.jsx("p",{className:"text-xs text-muted",children:valid?`Новый фрагмент: ${sourceTimeText(a)} → ${sourceTimeText(b)} · ${(b-a).toFixed(2)} с. Субтитры для новых секунд обновятся автоматически.`:"Проверьте время: начало должно быть раньше конца, обе границы — внутри исходника."}),
    disabled&&jsxRuntimeExports.jsx("p",{className:"text-xs text-amber-400",children:"Сначала примените или сбросьте текущие несохранённые правки на шкале."}),
    jsxRuntimeExports.jsxs("div",{className:"flex flex-wrap gap-2",children:[jsxRuntimeExports.jsx("button",{type:"button",className:"btn-accent",disabled:locked||!valid||(a===clip.start_s&&b===clip.end_s),onClick:()=>void apply(),children:busy?"Запуск…":active?"Расширение клипа…":"Применить новые границы"}),jsxRuntimeExports.jsx("button",{type:"button",className:"btn-ghost",disabled:locked,onClick:()=>{setStart(sourceTimeText(clip.start_s));setEnd(sourceTimeText(clip.end_s));setError("");},children:"Вернуть границы"})]}),
    error&&jsxRuntimeExports.jsx("p",{role:"alert",className:"text-sm text-error",children:error}),
    job&&jsxRuntimeExports.jsx("p",{"aria-live":"polite",className:"text-xs text-muted",children:`Задание ${job.id}: ${job.status}. ${job.status==="done"?"Готово — откройте обновлённый клип, шкала включает новый диапазон.":"Клип будет заново нарезан из исходника."}`})
  ]});
}
