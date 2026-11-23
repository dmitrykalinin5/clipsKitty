function isProfanityToken(word) {
  const token=normToken(word).replace(/ё/g,"е");
  if(PROFANITY.has(token))return true;
  return /^(?:(?:за|вы|по|под|на|от|об|раз|пере|про|до|у|с|в|при|недо|не|ни|без|из|ис|о|вз|повы)?(?:еб|пизд|пезд|бляд|блят)[а-я]*|(?:на|по|за|до|ни|не|о|а)?ху[йяеи][а-я]*|бля|су(?:ка|ки|ке|ку|кой|к)|суч(?:ка|ки|ке|ку|кой|енок|онок|ара)[а-я]*|долбоеб[а-я]*|муда(?:к|ки|ков|ком|ч)[а-я]*|мудил[а-я]*|пид(?:ор|ар)[а-я]*)$/.test(token);
}
function centerCensorRange(word,duration) {
  const start=Math.max(0,Number(word.start)),end=Math.min(duration,Number(word.end));
  if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start)return null;
  const edge=(end-start)*0.25;
  const a=Math.round((start+edge)*1000)/1000,b=Math.round((end-edge)*1000)/1000;
  return b>a?[a,b]:null;
}
function sameCensorRange(a,b) {
  return a&&b&&Math.abs(a[0]-b[0])<0.012&&Math.abs(a[1]-b[1])<0.012;
}
function fullWordRange(word,duration) {
  return [Math.round(Math.max(0,word.start-0.04)*100)/100,Math.round(Math.min(duration,word.end+0.04)*100)/100];
}
function censorWordCenters(edit,words,duration) {
  const flagged=words.filter(w=>isProfanityToken(w.word)&&centerCensorRange(w,duration));
  let mutes=[...edit.mutes],muted=[...edit.muted_words];
  for(const word of flagged){
    const center=centerCensorRange(word,duration),full=fullWordRange(word,duration);
    mutes=mutes.filter(range=>!sameCensorRange(range,full)&&!sameCensorRange(range,center));
    mutes.push(center);
    if(!muted.some(m=>Math.abs(m.start-word.start)<0.03&&m.word===word.word))muted.push({start:word.start,end:word.end,word:word.word});
  }
  return {edit:{...edit,mutes:mutes.sort((a,b)=>a[0]-b[0]),muted_words:muted},count:flagged.length};
}
