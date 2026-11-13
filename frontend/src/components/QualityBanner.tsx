'use client';
import React from 'react';
import { AlertCircle, CheckCircle2, RefreshCw, Sun, Eye, Crop } from 'lucide-react';
import { ImageQualityAssessment } from '../lib/types';

interface QualityBannerProps {
  frontQuality?: ImageQualityAssessment;
  backQuality?: ImageQualityAssessment;
  onRetry?: () => void;
}

export const QualityBanner: React.FC<QualityBannerProps> = ({
  frontQuality,
  backQuality,
  onRetry,
}) => {
  if (!frontQuality) return null;

  const isFrontPoor = !frontQuality.is_acceptable;
  const isBackPoor = backQuality && !backQuality.is_acceptable;
  const hasIssues = isFrontPoor || isBackPoor;

  return (
    <div
      className={`p-4 rounded-2xl border transition-all ${
        hasIssues
          ? 'bg-amber-50/80 border-amber-200 text-amber-900'
          : 'bg-emerald-50/80 border-emerald-200 text-emerald-900'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {hasIssues ? (
            <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
          ) : (
            <CheckCircle2 className="w-5 h-5 text-emerald-600 mt-0.5 shrink-0" />
          )}
          <div>
            <h4 className="font-semibold text-sm">
              {hasIssues
                ? 'Image Quality Notice: Better Photo Recommended'
                : 'Document Quality Check Passed'}
            </h4>
            <p className="text-xs mt-1 text-slate-600">
              {hasIssues
                ? 'Clearer photos improve OCR extraction and reduce false mismatches.'
                : 'Lighting and clarity meet minimum testing thresholds.'}
            </p>
          </div>
        </div>

        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-700 hover:bg-slate-50 transition shadow-sm"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Upload New Photo
          </button>
        )}
      </div>

      {/* Signal Badges */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3 pt-3 border-t border-slate-200/60">
        <div className="flex items-center gap-2 p-2 rounded-xl bg-white/70 border border-slate-200/50">
          <Eye className={`w-4 h-4 ${frontQuality.is_blurry ? 'text-amber-500' : 'text-emerald-500'}`} />
          <div className="text-xs">
            <span className="text-slate-500 block">Sharpness</span>
            <span className="font-semibold text-slate-800">
              {frontQuality.is_blurry ? 'Blurry' : 'Sharp'} ({frontQuality.blur_score})
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 p-2 rounded-xl bg-white/70 border border-slate-200/50">
          <Sun className={`w-4 h-4 ${frontQuality.is_dark || frontQuality.is_glare ? 'text-amber-500' : 'text-emerald-500'}`} />
          <div className="text-xs">
            <span className="text-slate-500 block">Lighting</span>
            <span className="font-semibold text-slate-800">
              {frontQuality.is_dark ? 'Too Dark' : frontQuality.is_glare ? 'Glare Detected' : 'Well Lit'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 p-2 rounded-xl bg-white/70 border border-slate-200/50">
          <Crop className={`w-4 h-4 ${frontQuality.is_cropped_suspected ? 'text-amber-500' : 'text-emerald-500'}`} />
          <div className="text-xs">
            <span className="text-slate-500 block">Framing</span>
            <span className="font-semibold text-slate-800">
              {frontQuality.is_cropped_suspected ? 'Suspected Crop' : 'Normal Aspect'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 p-2 rounded-xl bg-white/70 border border-slate-200/50">
          <div className="text-xs">
            <span className="text-slate-500 block">Dimensions</span>
            <span className="font-semibold text-slate-800">
              {frontQuality.width} × {frontQuality.height} px
            </span>
          </div>
        </div>
      </div>

      {/* Actionable recommendations */}
      {frontQuality.recommendations.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs text-amber-800 bg-amber-100/50 p-2.5 rounded-xl border border-amber-200/50">
          {frontQuality.recommendations.map((rec, idx) => (
            <li key={idx} className="flex items-center gap-1.5">
              <span>•</span>
              <span>{rec}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
