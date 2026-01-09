'use client';

import { useCallback, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Search, FileText, Link as LinkIcon, Layers3, Sparkles } from 'lucide-react';
import { useEffect } from "react";

type PdfSource = {
  pdf_id: string;
  pdf_path: string;
  page_no: number;
  chunk_id: number;
  chunk_profile?: string;
  pdf_url: string;
  viewer_url: string;
  page_image_url: string;
  snippet?: string;
};

type AskResponse = {
  answer: string;
  sources: PdfSource[];
};

export default function PdfRagClient() {
  const [question, setQuestion] = useState('');
  const [topK, setTopK] = useState<number>(10);
  const [pdfId, setPdfId] = useState<string>('');

  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<AskResponse | null>(null);
  const [selected, setSelected] = useState<PdfSource | null>(null);

  const totalSources = data?.sources?.length ?? 0;
  const selectedLabel = useMemo(() => {
    if (!selected) return '근거를 선택하면 PDF가 표시됩니다.';
    return `${selected.pdf_id} · p.${selected.page_no + 1} · chunk ${selected.chunk_id}`;
  }, [selected]);


useEffect(() => {
  if (selected) {
    console.log("selected.page_image_url =", selected.page_image_url);
    console.log("selected.viewer_url =", selected.viewer_url);
  }
}, [selected]);

  const profileDist = useMemo(() => {
    const dist: Record<string, number> = {};
    for (const s of data?.sources ?? []) {
      const key = s.chunk_profile ?? 'unknown';
      dist[key] = (dist[key] ?? 0) + 1;
    }
    return dist;
  }, [data]);

  const handleAsk = useCallback(async () => {
    if (!question.trim()) return;

    setLoading(true);
    setData(null);
    setSelected(null);

    try {
      const res = await fetch('/pdf/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          top_k: topK,
          pdf_id: pdfId.trim() ? pdfId.trim() : null,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err?.detail || err?.error || `요청 실패 (HTTP ${res.status})`);
        return;
      }

      const json: AskResponse = await res.json();
      setData(json);
      setSelected(json.sources?.[0] ?? null);
    } catch (e: any) {
      alert(e?.message ?? '요청 실패');
    } finally {
      setLoading(false);
    }
  }, [question, topK, pdfId]);

  return (
    <div className="min-h-screen bg-white">
      {/* 상단 헤더 */}
      <motion.div
        className="bg-gradient-to-b from-white to-blue-50/10 border-b border-gray-100"
        initial={{ opacity: 0, y: -15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <div className="container mx-auto px-8 py-10 flex flex-col gap-8">
          {/* 라벨 */}
          <motion.div
            className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-4 py-1.5 text-sm w-fit"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, delay: 0.1 }}
          >
            <FileText className="mr-2 h-4 w-4 text-blue-600" />
            <span className="text-blue-700 font-medium">사내문서 RAG · PDF 근거 검증</span>
          </motion.div>

          {/* 타이틀 */}
          <div>
            <h1 className="text-4xl font-bold text-gray-900 tracking-tight">
              <span className="bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
                Document RAG
              </span>{' '}
              근거 기반 검색
            </h1>
            <p className="mt-2 text-gray-600 text-lg leading-relaxed">
              질문 → 답변 → 근거(PDF 페이지)로 바로 검증할 수 있는 RAG 콘솔입니다.
            </p>
          </div>

          {/* 컨트롤 카드 */}
          <motion.div
            className="bg-white border border-gray-100 rounded-xl shadow-sm px-6 py-5 flex flex-col gap-5"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            {/* 통계 */}
            <div className="flex flex-wrap items-center gap-8 text-gray-700 text-sm border-b border-gray-100 pb-4">
              <div className="flex items-center gap-2">
                <span className="text-blue-600 font-semibold">근거 수</span>
                <span>{totalSources}개</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-blue-600 font-semibold">선택된 근거</span>
                <span className="text-gray-600">{selected ? `p.${selected.page_no + 1}` : '-'}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-blue-600 font-semibold">Top-K</span>
                <span>{topK}</span>
              </div>
            </div>

            {/* 입력 영역 */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
              <div className="lg:col-span-7">
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="예) 복리후생 제도에서 건강검진 지원 기준은?"
                  className="w-full min-h-[88px] rounded-md border border-gray-300 px-3 py-2 text-sm
                             focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                />
              </div>

              <div className="lg:col-span-5 flex flex-col gap-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Top-K</div>
                    <input
                      type="number"
                      value={topK}
                      onChange={(e) => setTopK(Number(e.target.value))}
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm
                                 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                      min={1}
                      max={50}
                    />
                  </div>

                  <div>
                    <div className="text-xs text-gray-500 mb-1">pdf_id 제한(선택)</div>
                    <input
                      value={pdfId}
                      onChange={(e) => setPdfId(e.target.value)}
                      placeholder="특정 문서만 검색"
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm
                                 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
                    />
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleAsk}
                  disabled={loading || !question.trim()}
                  className="inline-flex items-center justify-center gap-2 px-3 py-2
                             text-white bg-gradient-to-r from-blue-600 to-purple-600
                             hover:from-blue-700 hover:to-purple-700
                             shadow-sm hover:shadow-md
                             rounded-md text-sm font-medium transition-all duration-200
                             disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <Sparkles className="w-4 h-4 animate-pulse" />
                      검색 중...
                    </>
                  ) : (
                    <>
                      <Search className="w-4 h-4" />
                      검색
                    </>
                  )}
                </button>

                <div className="text-xs text-gray-500">
                  팁: <span className="font-semibold text-blue-700">fragmented_text</span> 문서가 많으면 Top-K를 10~15로 올려보세요.
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </motion.div>

      {/* 본문 */}
      <div className="container mx-auto px-8 mt-8 grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* 좌측: 답변 + 근거 */}
        <div className="xl:col-span-5 flex flex-col gap-6">
          {/* 답변 카드 */}
          <div className="bg-white border border-gray-100 rounded-xl shadow-sm p-6">
            <div className="flex items-center gap-2 mb-2">
              <Layers3 className="w-4 h-4 text-blue-600" />
              <div className="text-sm font-semibold text-gray-900">AI 답변</div>
            </div>
            <div className="text-sm text-gray-700 whitespace-pre-wrap">
              {data?.answer || (loading ? '답변 생성 중…' : '질문을 입력하고 검색하면 답변이 표시됩니다.')}
            </div>
          </div>

          {/* 근거 카드 */}
          <div className="bg-white border border-gray-100 rounded-xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-600" />
                <div className="text-sm font-semibold text-gray-900">근거 문서</div>
              </div>
              <div className="text-xs text-gray-500">{totalSources}개</div>
            </div>

            {/* profile 분포 (간단 배지) */}
            {Object.keys(profileDist).length > 0 && (
              <div className="flex flex-wrap gap-2 mb-4">
                {Object.entries(profileDist).map(([k, v]) => (
                  <span
                    key={k}
                    className="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs text-gray-700"
                  >
                    {k} · {v}
                  </span>
                ))}
              </div>
            )}

            <div className="max-h-[420px] overflow-auto pr-1">
              {(data?.sources ?? []).map((s) => {
                const active = selected?.pdf_id === s.pdf_id && selected?.chunk_id === s.chunk_id;
                return (
                  <button
                    key={`${s.pdf_id}:${s.chunk_id}`}
                    onClick={() => setSelected(s)}
                    className={`w-full text-left rounded-lg border px-4 py-3 mb-2 transition
                      ${active ? 'border-blue-300 bg-blue-50/40' : 'border-gray-100 hover:bg-gray-50'}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-gray-900 truncate">{s.pdf_id}</div>
                        <div className="text-xs text-gray-500 mt-1">
                          p.{s.page_no + 1} · chunk {s.chunk_id}
                          {s.chunk_profile ? ` · ${s.chunk_profile}` : ''}
                        </div>
                      </div>

                      <a
                        href={s.viewer_url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="shrink-0 inline-flex items-center justify-center w-9 h-9 rounded-md
                                   border border-gray-200 bg-white hover:bg-gray-50"
                        title="새 탭에서 열기"
                      >
                        <LinkIcon className="w-4 h-4 text-gray-700" />
                      </a>
                    </div>

                    {s.snippet ? (
                      <div className="mt-2 text-xs text-gray-600 line-clamp-3">
                        {s.snippet}
                      </div>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* 우측: PDF 뷰어 */}
        <div className="xl:col-span-7">
          <div className="bg-white border border-gray-100 rounded-xl shadow-sm p-6">
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="text-sm font-semibold text-gray-900">PDF 뷰어</div>
                <div className="text-xs text-gray-500 mt-1">{selectedLabel}</div>
              </div>

              {selected && (
                <a href={selected.viewer_url} target="_blank" rel="noreferrer">
                  <button
                    className="inline-flex items-center gap-1.5 px-3 py-1.5
                               text-gray-700 border border-gray-200 bg-white
                               hover:bg-gray-50 rounded-md text-sm font-medium transition"
                  >
                    <LinkIcon className="w-4 h-4" />
                    새 탭
                  </button>
                </a>
              )}
            </div>

            <div className="w-full h-[780px] rounded-lg border border-gray-100 overflow-hidden bg-gray-50">
              {selected?.page_image_url ? (
  <img
    src={selected.page_image_url}
    alt="PDF page"
    className="w-full h-full object-contain bg-white"
  />
): (
                <div className="h-full flex items-center justify-center text-sm text-gray-400">
                  근거를 선택하면 PDF 페이지가 표시됩니다.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-8 py-10 text-xs text-gray-400">
        사내문서 RAG 프로젝트 · 근거 기반 검증 UI
      </div>
    </div>
  );
}
