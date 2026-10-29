import type { PageInfo, PageParams } from '../types/api';
export const rangeLabel=(info:PageInfo,language:string)=>{
  const start=info.total && info.page<=info.total_pages ? (info.page-1)*info.page_size+1 : 0;
  const end=info.page<=info.total_pages ? Math.min(info.page*info.page_size,info.total) : 0;
  const number=(value:number)=>value.toLocaleString(language==='it'?'it-IT':'en-GB');
  return language==='it' ? `Mostrati ${number(start)}–${number(end)} di ${number(info.total)} osservazioni`
    : `Showing ${number(start)}–${number(end)} of ${number(info.total)} observations`;
};
export function PaginationControls({info,language,loading,onChange}:{info:PageInfo;language:string;loading:boolean;onChange:(params:PageParams)=>void}){
  return <div className="p-3 border-t border-[#E5E7EB] bg-[#F8F9FA] flex flex-wrap items-center justify-between gap-3 text-xs text-[#4B5563]">
    <span>{rangeLabel(info,language)}</span>
    <div className="flex items-center gap-2">
      <label>{language==='it'?'Risultati per pagina':'Results per page'}{' '}
        <select aria-label={language==='it'?'Risultati per pagina':'Results per page'} value={info.page_size} disabled={loading}
          onChange={event=>onChange({page_size:Number(event.target.value) as 10|20|50,page:1})} className="rounded border p-1 bg-white">
          {[10,20,50].map(value=><option key={value} value={value}>{value}</option>)}
        </select>
      </label>
      <button disabled={loading||info.page<=1} onClick={()=>onChange({page:info.page-1})} className="px-2 py-1 rounded border bg-white disabled:opacity-40">{language==='it'?'Precedente':'Previous'}</button>
      <span>{language==='it'?'Pagina':'Page'} {info.page} / {info.total_pages}</span>
      <button disabled={loading||info.page>=info.total_pages} onClick={()=>onChange({page:info.page+1})} className="px-2 py-1 rounded border bg-white disabled:opacity-40">{language==='it'?'Successiva':'Next'}</button>
    </div>
  </div>;
}
