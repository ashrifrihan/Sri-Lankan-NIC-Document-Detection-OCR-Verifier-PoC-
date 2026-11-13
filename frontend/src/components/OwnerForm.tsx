'use client';
import React, { useState, useEffect } from 'react';
import { User, CreditCard, Calendar, CheckCircle2, AlertCircle, Sparkles } from 'lucide-react';
import { NICValidationResult } from '../lib/types';
import { validateNIC } from '../lib/api';

interface OwnerFormProps {
  fullName: string;
  nicNumber: string;
  dob: string;
  onFullNameChange: (val: string) => void;
  onNicNumberChange: (val: string) => void;
  onDobChange: (val: string) => void;
  onAutoFillDob?: (dob: string) => void;
}

export const OwnerForm: React.FC<OwnerFormProps> = ({
  fullName,
  nicNumber,
  dob,
  onFullNameChange,
  onNicNumberChange,
  onDobChange,
  onAutoFillDob,
}) => {
  const [nicFeedback, setNicFeedback] = useState<NICValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState(false);

  useEffect(() => {
    const clean = nicNumber.trim();
    if (clean.length >= 9) {
      setIsValidating(true);
      const timer = setTimeout(async () => {
        try {
          const res = await validateNIC(clean);
          setNicFeedback(res);
        } catch (e) {
          setNicFeedback(null);
        } finally {
          setIsValidating(false);
        }
      }, 300);
      return () => clearTimeout(timer);
    } else {
      setNicFeedback(null);
    }
  }, [nicNumber]);

  return (
    <div className="bg-white/80 backdrop-blur rounded-2xl p-5 border border-slate-200/80 shadow-sm space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <h3 className="font-semibold text-slate-800 text-sm flex items-center gap-2">
          <User className="w-4 h-4 text-slate-500" />
          Owner Information (For Verification Matching)
        </h3>
        <span className="text-[11px] text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
          Provisional Testing Mode
        </span>
      </div>

      <div className="space-y-3">
        {/* Full Name */}
        <div>
          <label className="text-xs font-semibold text-slate-700 block mb-1">
            Full Name (with initials or expanded)
          </label>
          <div className="relative">
            <input
              type="text"
              placeholder="e.g. K. A. Perera or Kamal Anuradha Perera"
              value={fullName}
              onChange={(e) => onFullNameChange(e.target.value)}
              className="w-full px-3.5 py-2 text-sm bg-slate-50/50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition"
            />
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            Accepts initials (K.A. Perera) or full names. Sinhala/Tamil transliterated names supported.
          </p>
        </div>

        {/* NIC Number */}
        <div>
          <label className="text-xs font-semibold text-slate-700 block mb-1">
            National Identity Card (NIC) Number
          </label>
          <div className="relative">
            <input
              type="text"
              placeholder="e.g. 853451234V or 198534501234"
              value={nicNumber}
              onChange={(e) => onNicNumberChange(e.target.value.toUpperCase())}
              className={`w-full px-3.5 py-2 text-sm bg-slate-50/50 border rounded-xl focus:outline-none focus:ring-2 transition uppercase font-mono ${
                nicFeedback?.is_valid
                  ? 'border-emerald-300 focus:ring-emerald-500/10'
                  : nicNumber.length >= 9
                  ? 'border-amber-300 focus:ring-amber-500/10'
                  : 'border-slate-200 focus:ring-slate-900/10'
              }`}
            />
            {nicFeedback?.is_valid && (
              <CheckCircle2 className="w-4 h-4 text-emerald-500 absolute right-3 top-2.5" />
            )}
          </div>

          {/* Real-time Sri Lankan NIC Decoder Pill */}
          {nicFeedback && (
            <div
              className={`mt-2 p-2.5 rounded-xl text-xs border transition-all ${
                nicFeedback.is_valid
                  ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                  : 'bg-amber-50/70 border-amber-200 text-amber-900'
              }`}
            >
              {nicFeedback.is_valid ? (
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-emerald-800">
                      {nicFeedback.format === 'old_9_digit' ? 'Old 9-Digit + V/X' : 'New 12-Digit Format'}
                    </span>
                    <span>•</span>
                    <span>Gender: <strong>{nicFeedback.gender}</strong></span>
                    <span>•</span>
                    <span>Encoded Birth Year: <strong>{nicFeedback.birth_year}</strong></span>
                  </div>

                  {nicFeedback.decoded_dob && (
                    <div className="flex items-center justify-between pt-1 border-t border-emerald-200/50">
                      <span>Encoded DOB: <strong>{nicFeedback.decoded_dob}</strong></span>
                      {onAutoFillDob && dob !== nicFeedback.decoded_dob && (
                        <button
                          type="button"
                          onClick={() => onAutoFillDob(nicFeedback.decoded_dob!)}
                          className="flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-white px-2 py-0.5 rounded-lg border border-emerald-300 shadow-2xs hover:bg-emerald-100/50"
                        >
                          <Sparkles className="w-3 h-3 text-emerald-600" />
                          Auto-fill DOB
                        </button>
                      )}
                    </div>
                  )}

                  {nicFeedback.equivalent_alternate_format && (
                    <p className="text-[11px] text-emerald-700">
                      Equivalent format: <code className="font-mono bg-white/60 px-1 py-0.5 rounded">{nicFeedback.equivalent_alternate_format}</code>
                    </p>
                  )}
                </div>
              ) : (
                <div className="flex items-start gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 text-amber-600 mt-0.5 shrink-0" />
                  <div>
                    {nicFeedback.errors.map((err, idx) => (
                      <p key={idx}>{err}</p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Date of Birth */}
        <div>
          <label className="text-xs font-semibold text-slate-700 block mb-1">
            Date of Birth (YYYY-MM-DD)
          </label>
          <div className="relative">
            <input
              type="date"
              value={dob}
              onChange={(e) => onDobChange(e.target.value)}
              className="w-full px-3.5 py-2 text-sm bg-slate-50/50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition"
            />
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            Validated against the encoded day-of-year in the Sri Lankan NIC number.
          </p>
        </div>
      </div>
    </div>
  );
};
