'use client';
import React, { useState } from 'react';
import { AlertTriangle, ShieldCheck, X } from 'lucide-react';

interface DisclaimerProps {
  isOpenByDefault?: boolean;
}

export const DisclaimerModal: React.FC<DisclaimerProps> = ({ isOpenByDefault = false }) => {
  const [isOpen, setIsOpen] = useState(isOpenByDefault);

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="text-xs text-slate-500 hover:text-slate-800 underline transition-colors"
      >
        PoC Compliance & Safety Notice
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-slate-200">
            <div className="flex items-start justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-amber-100 text-amber-800 rounded-xl">
                  <AlertTriangle className="w-5 h-5" />
                </div>
                <h3 className="font-semibold text-slate-900 text-lg">
                  Experimental Proof of Concept Notice
                </h3>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mt-4 space-y-3 text-sm text-slate-600 leading-relaxed">
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 font-medium text-xs">
                ⚠️ Strictly for testing Sri Lankan NIC image detection and OCR capabilities. Not an official identity verification authority.
              </div>
              <p>
                <strong>1. No Guarantee of Genuineness:</strong> Automated OCR and heuristic classification can never ascertain the physical authenticity or tamper-free state of an identity document.
              </p>
              <p>
                <strong>2. Provisional Heuristics:</strong> Document category detection (old laminated, printed laminated, newer smart card) relies on baseline visual and textual heuristics without claiming certified model precision.
              </p>
              <p>
                <strong>3. Transliteration & Names:</strong> Sinhala and Tamil names may exhibit legitimate transliteration differences; matches are conservative and mark ambiguities as uncertain rather than guessing.
              </p>
              <p>
                <strong>4. Mandatory Human Review:</strong> All identity decisions must rest with qualified human administrators.
              </p>
              <p>
                <strong>5. Local Privacy:</strong> All image analysis is processed in-memory or ephemeral storage on your local machine and immediately discarded.
              </p>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setIsOpen(false)}
                className="px-5 py-2.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-medium text-sm transition-all"
              >
                I Understand & Acknowledge
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
