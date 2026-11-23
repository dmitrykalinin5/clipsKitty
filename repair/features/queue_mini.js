function miniQueueView(snapshot, detail) {
  const running=snapshot?.processing??[], waiting=snapshot?.queued??[];
  const job=running[0]??waiting[0];
  if(!job)return null;
  const active=running.length>0;
  const progress=active&&detail?.id===job.id?detail.progress:null;
  const percent=Number.isFinite(progress?.percent)?Math.max(0,Math.min(100,Math.round(progress.percent))):null;
  return {job,active,percent,waiting:waiting.length,running:running.length,
    title:jobLabel(job),
    label:active?(progress?.label||"Подготовка задачи…"):(snapshot.paused?"Очередь приостановлена":"Ожидает запуска"),
    eta:active&&Number.isFinite(progress?.eta_seconds)?Math.max(0,progress.eta_seconds):null};
}
function QueueMiniWindow() {
  const [snapshot,setSnapshot]=reactExports.useState(null);
  const [detail,setDetail]=reactExports.useState(null);
  const [offline,setOffline]=reactExports.useState(false);
  const [collapsed,setCollapsed]=reactExports.useState(false);
  const refreshRef=reactExports.useRef(()=>{});
  reactExports.useEffect(()=>{
    let closed=false,busy=false;
    const refresh=async()=>{
      if(closed||busy)return;
      busy=true;
      try {
        const next=await api.queue();
        if(closed)return;
        setSnapshot(next);
        const job=next.processing?.[0];
        if(job){
          const current=await request$1(`/jobs/${job.id}`);
          if(!closed)setDetail(current);
        }else setDetail(null);
        if(!closed)setOffline(false);
      }catch{if(!closed)setOffline(true);}
      finally{busy=false;}
    };
    refreshRef.current=refresh;
    void refresh();
    const timer=setInterval(refresh,2000);
    return ()=>{closed=true;clearInterval(timer);refreshRef.current=()=>{};};
  },[]);
  useEvents(e=>{
    if(e.type==="job"||e.type==="queue")void refreshRef.current();
  });
  const view=miniQueueView(snapshot,detail);
  if(!view)return null;
  const open=()=>window.dispatchEvent(new CustomEvent("open-queue"));
  return jsxRuntimeExports.jsxs("section",{
    "aria-label":"Текущая задача очереди",
    className:"bg-surface border border-raised rounded-lg shadow-xl text-ink",
    style:{position:"fixed",right:16,bottom:16,zIndex:45,width:collapsed?250:330,maxWidth:"calc(100vw - 32px)",padding:12},
    children:[
      jsxRuntimeExports.jsxs("div",{className:"flex items-center gap-2",children:[
        jsxRuntimeExports.jsx("button",{type:"button",onClick:open,className:"text-xs font-semibold text-accent flex-1 text-left",children:`${view.active?"Сейчас в работе":"Очередь"}${view.percent!==null?` · ${view.percent}%`:""}`}),
        jsxRuntimeExports.jsx("button",{type:"button",onClick:()=>setCollapsed(v=>!v),className:"text-muted text-xs",title:collapsed?"Развернуть прогресс":"Свернуть прогресс","aria-label":collapsed?"Развернуть прогресс":"Свернуть прогресс","aria-expanded":!collapsed,children:collapsed?"▴":"▾"})
      ]}),
      jsxRuntimeExports.jsx("button",{type:"button",onClick:open,className:"block w-full text-left text-sm truncate mt-1",title:view.title,children:view.title}),
      !collapsed&&jsxRuntimeExports.jsxs(jsxRuntimeExports.Fragment,{children:[
        jsxRuntimeExports.jsx("p",{className:"text-xs text-muted truncate mt-1",title:view.label,children:offline?"Нет связи — обновление прогресса…":view.label}),
        jsxRuntimeExports.jsx("div",{role:"progressbar","aria-label":"Прогресс текущей задачи","aria-valuemin":0,"aria-valuemax":100,...(view.percent!==null?{"aria-valuenow":view.percent}:{}),className:"mt-2 h-1.5 rounded-full bg-raised overflow-hidden",children:jsxRuntimeExports.jsx("div",{className:`h-full bg-accent${view.active&&view.percent===null?" animate-pulse":""}`,style:{width:`${view.percent??(view.active?25:0)}%`,transition:"width 0.4s"}})}),
        jsxRuntimeExports.jsxs("div",{className:"flex items-center justify-between text-xs text-muted mt-2",children:[
          jsxRuntimeExports.jsx("span",{children:`Ожидают: ${view.waiting}${view.running>1?` · В работе: ${view.running}`:""}`}),
          jsxRuntimeExports.jsx("button",{type:"button",onClick:open,className:"text-accent",children:"Открыть очередь →"})
        ]}),
        view.eta!==null&&!offline&&jsxRuntimeExports.jsx("p",{className:"text-xs text-muted mt-1",children:`Примерно осталось: ${formatQueueEta(view.eta)}`})
      ]})
    ]
  });
}
