'use client';
import React, { useRef, useState } from 'react';
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  HelpCircle,
  FileText,
  ShieldAlert,
  UserCheck,
  Info,
  Calendar,
  CreditCard,
  User,
  Sparkles,
  ArrowRight,
  ClipboardCopy
} from 'lucide-react';
import { VerificationResponse, MatchStatus } from '../lib/types';
import { QualityBanner } from './QualityBanner';
import { trainAnalysis } from '../lib/api';

interface ResultsViewProps {
  result: VerificationResponse;
  frontPreview?: string | null;
  backPreview?: string | null;
  onReset: () => void;
  onApplyExtractedToForm?: (nic: string, name: string, dob: string) => void;
}

export const ResultsView: React.FC<ResultsViewProps> = ({
  result,
  frontPreview,
  backPreview,
  onReset,
  onApplyExtractedToForm
}) => {
  const [confirmedNIC, setConfirmedNIC] = useState(result.extracted_nic ?? '');
  const [confirmedName, setConfirmedName] = useState(result.extracted_name ?? '');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [reviewSide, setReviewSide] = useState<'front' | 'back'>('front');
  const [zoom, setZoom] = useState(100);
  const [focus, setFocus] = useState<{ x: number; y: number } | null>(null);
  const review = useRef<HTMLDetailsElement>(null);
  const reviewPhoto = reviewSide === 'front' ? frontPreview : backPreview;

  function inspectField(field: 'nic' | 'name' | 'dob') {
    const oldCard = /[VX]$/i.test(result.extracted_nic ?? '');
    const regions = { nic: { x: .62, y: .22 }, name: { x: .65, y: .65 }, dob: { x: .75, y: .85 } };
    setReviewSide('front');
    setFocus(oldCard ? field === 'nic' ? { x: .5, y: .35 } : null : regions[field]);
    setZoom(oldCard && field !== 'nic' ? 100 : 225);
    if (review.current) {
      review.current.open = true;
      review.current.scrollIntoView({ block: 'nearest' });
    }
  }

  const handleTraining = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setFeedback('');
    try {
      await trainAnalysis(result.request_id, confirmedNIC, confirmedName);
      setSaved(true);
      setFeedback('Saved to your local analysis model.');
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : 'Could not save training feedback.');
    } finally {
      setSaving(false);
    }
  };

  const getStatusBadge = (status: MatchStatus) => {
    switch (status) {
      case 'match':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
            <CheckCircle className="w-3.5 h-3.5" /> Match
          </span>
        );
      case 'partial_match':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
            <Info className="w-3.5 h-3.5" /> Partial Match
          </span>
        );
      case 'uncertain':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
            <HelpCircle className="w-3.5 h-3.5" /> Uncertain
          </span>
        );
      case 'mismatch':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-800">
            <XCircle className="w-3.5 h-3.5" /> Mismatch
          </span>
        );
      case 'unavailable':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-600">
            No Form Input
          </span>
        );
    }
  };

  const getCategoryLabel = (cat: string) => {
    switch (cat) {
      case 'old_laminated':
        return 'Classic Laminated Paper (Pre-2016)';
      case 'printed_laminated':
        return 'Computer-Printed Laminated Card';
      case 'newer_plastic_card':
        return 'Modern Polycarbonate Card (12-Digit)';
      default:
        return 'Uncertain / Indeterminate Subtype';
    }
  };

  const isFormEmpty = !result.matches.nic.form_value && !result.matches.name.form_value && !result.matches.dob.form_value;
  const hasExtractedData = Boolean(result.extracted_nic || result.extracted_name || result.extracted_dob);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Quality Banner */}
      <QualityBanner
        frontQuality={result.front_quality}
        backQuality={result.back_quality}
        onRetry={onReset}
      />
      {result.review_status && <p className="text-sm font-semibold text-slate-700">
        {{ readable: 'Readable', retake_needed: 'Retake needed', manual_review: 'Manual review' }[result.review_status]}
      </p>}

      {reviewPhoto && (
        <details ref={review} className="rounded-2xl border border-slate-200 bg-white p-5">
          <summary className="cursor-pointer text-sm font-semibold">Inspect the uploaded photo</summary>
          <div className="mt-3 flex flex-wrap gap-4 text-sm">
            {backPreview && <label>Side{' '}
              <select value={reviewSide} onChange={(event) => {
                setFocus(null);
                setReviewSide(event.target.value === 'back' ? 'back' : 'front');
              }}>
                <option value="front">Front</option>
                <option value="back">Back</option>
              </select>
            </label>}
            <label>Zoom {zoom}%{' '}
              <input type="range" min={100} max={300} step={25} value={zoom} onChange={(event) => setZoom(Number(event.target.value))} />
            </label>
          </div>
          <div className="mt-3 max-h-[60vh] overflow-auto rounded-lg bg-slate-100" tabIndex={0} aria-label="Scrollable NIC photo">
            <img src={reviewPhoto} alt={`Uploaded NIC ${reviewSide}`} style={{ width: `${zoom}%`, maxWidth: 'none' }}
              ref={(image) => {
                const panel = image?.parentElement;
                if (image && panel && focus) requestAnimationFrame(() => {
                  panel.scrollTo(image.width * focus.x - panel.clientWidth / 2, image.height * focus.y - panel.clientHeight / 2);
                });
              }} />
          </div>
        </details>
      )}

      {result.can_train && (
        <form onSubmit={handleTraining} className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3">
          <h2 className="text-sm font-semibold text-slate-800">Train your local analysis model</h2>
          <p className="text-xs text-slate-600">Check both values against the card. Leave any field you cannot confirm blank.</p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="grid gap-1 text-xs font-medium text-slate-700">
              Confirmed NIC number
              <input value={confirmedNIC} onChange={(event) => setConfirmedNIC(event.target.value)}
                maxLength={20} autoComplete="off" disabled={saving || saved}
                className="rounded-lg border border-slate-300 px-3 py-2" />
            </label>
            <label className="grid gap-1 text-xs font-medium text-slate-700">
              Confirmed full name
              <input value={confirmedName} onChange={(event) => setConfirmedName(event.target.value)}
                maxLength={180} autoComplete="off" disabled={saving || saved}
                className="rounded-lg border border-slate-300 px-3 py-2" />
            </label>
            <button type="submit" disabled={saving || saved || !(confirmedNIC.trim() || confirmedName.trim())} className="rounded-lg bg-slate-900 px-4 py-2 text-xs text-white disabled:opacity-50">
              {saving ? 'Saving…' : 'Save training feedback'}
            </button>
          </div>
          {feedback && <p role="status" className="text-xs text-slate-700">{feedback}</p>}
        </form>
      )}

      {/* Primary Verification Assessment Card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wider text-slate-500 font-bold">
                Overall Document Assessment
              </span>
              <span className="text-[10px] bg-amber-100 text-amber-900 font-bold px-2 py-0.5 rounded-full">
                Provisional Heuristic
              </span>
            </div>
            <h2 className="text-xl font-bold text-slate-900 mt-1">
              {result.overall_assessment}
            </h2>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onReset}
              className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-xs rounded-xl transition"
            >
              Test Another Document
            </button>
          </div>
        </div>

        {/* Classification and Visual Category Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <div className="p-4 rounded-xl bg-slate-50/70 border border-slate-100">
            <span className="text-xs text-slate-500 font-medium block">
              Document Type Detection
            </span>
            <div className="flex items-center gap-2 mt-1">
              <span
                className={`font-bold text-sm ${
                  result.front_classification.classification === 'sri_lankan_nic'
                    ? 'text-emerald-700'
                    : result.front_classification.classification === 'uncertain'
                    ? 'text-amber-700'
                    : 'text-rose-700'
                }`}
              >
                {result.front_classification.classification === 'sri_lankan_nic'
                  ? 'Sri Lankan NIC Detected'
                  : result.front_classification.classification === 'uncertain'
                  ? 'Uncertain Document'
                  : 'Not a Sri Lankan NIC'}
              </span>
              <span className="text-xs text-slate-400">
                (Confidence: {Math.round(result.front_classification.confidence * 100)}%)
              </span>
            </div>
            {result.front_classification.notes.length > 0 && (
              <p className="text-xs text-slate-600 mt-1.5">
                {result.front_classification.notes[0]}
              </p>
            )}
          </div>

          <div className="p-4 rounded-xl bg-slate-50/70 border border-slate-100">
            <span className="text-xs text-slate-500 font-medium block">
              Visual Category
            </span>
            <div className="flex items-center gap-2 mt-1">
              <span className="font-bold text-sm text-slate-800">
                {getCategoryLabel(result.front_classification.visual_category)}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1.5">
              Based on color palette distribution, security emblem, and optical structure heuristics.
            </p>
          </div>
        </div>
      </div>

      {/* Prominent Extracted Document Profile (OCR Values) */}
      <div className="bg-gradient-to-br from-slate-900 to-slate-800 text-white rounded-2xl p-6 shadow-md border border-slate-700 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-700/60 pb-3">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-emerald-500/20 text-emerald-400 rounded-xl">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-white">
                Extracted Document Profile (OCR Signals)
              </h3>
              <p className="text-xs text-slate-400">
                Values isolated directly from the card by optical character recognition
              </p>
            </div>
          </div>

          {onApplyExtractedToForm && hasExtractedData && (
            <button
              onClick={() => onApplyExtractedToForm(
                result.extracted_nic || '',
                result.extracted_name || '',
                result.extracted_dob || ''
              )}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition shadow-sm"
            >
              <ClipboardCopy className="w-3.5 h-3.5" />
              Copy to Form & Match
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Extracted NIC */}
          <div className="p-3.5 bg-slate-800/80 rounded-xl border border-slate-700">
            <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold block">
              Extracted NIC Number
            </span>
            <span className="text-lg font-mono font-bold text-emerald-400 block mt-1">
              {result.extracted_nic || <span className="text-slate-500 italic text-sm">Not Detected</span>}
            </span>
            {result.nic_validation && result.nic_validation.is_valid && (
              <div className="mt-2 pt-2 border-t border-slate-700/60 text-[11px] text-slate-300 space-y-0.5">
                <div>Format: <strong>{result.nic_validation.format === 'old_9_digit' ? 'Old 9-Digit (Pre-2016)' : 'New 12-Digit'}</strong></div>
                <div>Gender: <strong>{result.nic_validation.gender}</strong></div>
                <div>Birth Year: <strong>{result.nic_validation.birth_year}</strong></div>
              </div>
            )}
          </div>

          {/* Extracted Name */}
          <div className="p-3.5 bg-slate-800/80 rounded-xl border border-slate-700">
            <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold block">
              Extracted Full Name
            </span>
            <span className="text-sm font-bold text-white block mt-1 leading-snug">
              {result.extracted_name || <span className="text-slate-500 italic">Not Detected (or script text)</span>}
            </span>
            <p className="text-[11px] text-slate-400 mt-2">
              Official Latin transliteration from identity document.
            </p>
          </div>

          {/* Extracted Date of Birth */}
          <div className="p-3.5 bg-slate-800/80 rounded-xl border border-slate-700">
            <span className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold block">
              Extracted Date of Birth
            </span>
            <span className="text-base font-mono font-bold text-amber-300 block mt-1">
              {result.extracted_dob || <span className="text-slate-500 italic text-sm">Not Detected</span>}
            </span>
            {result.nic_validation?.decoded_dob && (
              <p className="text-[11px] text-slate-400 mt-2">
                Decoded from NIC: <strong className="text-slate-200">{result.nic_validation.decoded_dob}</strong>
              </p>
            )}
          </div>
        </div>

      </div>

      {/* Field-by-Field Comparison Matrix */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-slate-600" />
            {isFormEmpty ? 'Document reading results' : 'Field-by-field comparison'}
          </h3>

        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                <th className="pb-3 px-3">Field</th>
                {!isFormEmpty && <th className="pb-3 px-3">Form value</th>}
                <th className="pb-3 px-3">Extracted / Decoded Value</th>
                <th className="pb-3 px-3">Status</th>
                {!isFormEmpty && <th className="pb-3 px-3">Analysis & Reason</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {/* NIC Field */}
              <tr className="hover:bg-slate-50/50 transition">
                <td className="py-3 px-3 font-semibold text-slate-800 flex items-center gap-2">
                  <CreditCard className="w-4 h-4 text-slate-400" /> NIC Number
                </td>
                {!isFormEmpty && <td className="py-3 px-3 font-mono text-xs text-slate-700">
                  {result.matches.nic.form_value || <span className="text-slate-400 italic">Not provided</span>}
                </td>}
                <td className="py-3 px-3 font-mono text-xs font-bold text-slate-900">
                  {result.extracted_nic || <span className="text-slate-400 italic">—</span>}
                  {result.field_warnings?.nic && <p className="mt-1 text-amber-800">{result.field_warnings.nic}</p>}
                  {!!result.alternate_nic_reads?.length && <p className="mt-1">OCR readings: {result.alternate_nic_reads.join(' / ')}</p>}
                  {frontPreview && <button type="button" onClick={() => inspectField('nic')} className="mt-1 block underline">Check this field</button>}
                </td>
                <td className="py-3 px-3">{isFormEmpty ? (result.extracted_nic ? 'Available' : 'Could not read') : getStatusBadge(result.matches.nic.status)}</td>
                {!isFormEmpty && <td className="py-3 px-3 text-xs text-slate-600">
                  {result.matches.nic.reason}
                </td>}
              </tr>

              {/* Full Name Field */}
              <tr className="hover:bg-slate-50/50 transition">
                <td className="py-3 px-3 font-semibold text-slate-800 flex items-center gap-2">
                  <User className="w-4 h-4 text-slate-400" /> Full Name
                </td>
                {!isFormEmpty && <td className="py-3 px-3 text-xs text-slate-700">
                  {result.matches.name.form_value || <span className="text-slate-400 italic">Not provided</span>}
                </td>}
                <td className="py-3 px-3 text-xs font-bold text-slate-900">
                  {result.extracted_name || <span className="text-slate-400 italic">—</span>}
                  {result.field_warnings?.name && <p className="mt-1 text-amber-800">{result.field_warnings.name}</p>}
                  {frontPreview && <button type="button" onClick={() => inspectField('name')} className="mt-1 block underline">Check this field</button>}
                </td>
                <td className="py-3 px-3">{isFormEmpty ? (result.extracted_name ? 'Available' : 'Could not read') : getStatusBadge(result.matches.name.status)}</td>
                {!isFormEmpty && <td className="py-3 px-3 text-xs text-slate-600">
                  {result.matches.name.reason}
                </td>}
              </tr>

              {/* DOB Field */}
              <tr className="hover:bg-slate-50/50 transition">
                <td className="py-3 px-3 font-semibold text-slate-800 flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-slate-400" /> Date of Birth
                </td>
                {!isFormEmpty && <td className="py-3 px-3 font-mono text-xs text-slate-700">
                  {result.matches.dob.form_value || <span className="text-slate-400 italic">Not provided</span>}
                </td>}
                <td className="py-3 px-3 font-mono text-xs font-bold text-slate-900">
                  {result.extracted_dob || <span className="text-slate-400 italic">—</span>}
                  {result.dob_source && <p className="mt-1 font-normal text-slate-600">{result.dob_source === 'card' ? 'Read from photo' : 'Decoded from NIC number'}</p>}
                  {result.field_warnings?.dob && <p className="mt-1 text-amber-800">{result.field_warnings.dob}</p>}
                  {frontPreview && result.dob_source === 'card' && <button type="button" onClick={() => inspectField('dob')} className="mt-1 block underline">Check this field</button>}
                </td>
                <td className="py-3 px-3">{isFormEmpty ? (result.extracted_dob ? 'Available' : 'Could not read') : getStatusBadge(result.matches.dob.status)}</td>
                {!isFormEmpty && <td className="py-3 px-3 text-xs text-slate-600">
                  {result.matches.dob.reason}
                </td>}
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Critical Safety, Governance & Disclaimer Notice */}
      <div className="p-5 rounded-2xl bg-amber-50 border border-amber-300 text-amber-950">
        <div className="flex items-start gap-3">
          <ShieldAlert className="w-6 h-6 text-amber-700 shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs leading-relaxed">
            <h4 className="font-bold text-sm text-amber-900">
              Identity Verification Governance & Final Review Notice
            </h4>
            <p>
              {result.disclaimer}
            </p>
            <p className="font-semibold text-amber-900 pt-1">
              Decision Status: Administrative manual review required for any identity decision.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
