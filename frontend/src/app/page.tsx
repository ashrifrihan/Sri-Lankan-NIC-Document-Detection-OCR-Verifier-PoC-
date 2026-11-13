'use client';
import React, { useState, useEffect } from 'react';
import {
  Shield,
  UploadCloud,
  FileCheck,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  CheckCircle,
  ExternalLink,
  Laptop
} from 'lucide-react';
import { ImageUploader } from '../components/ImageUploader';
import { OwnerForm } from '../components/OwnerForm';
import { ResultsView } from '../components/ResultsView';
import { DisclaimerModal } from '../components/DisclaimerModal';
import { VerificationResponse } from '../lib/types';
import { verifyNICDocument, checkBackendHealth } from '../lib/api';

export default function Home() {
  // Files and previews
  const [frontFile, setFrontFile] = useState<File | null>(null);
  const [frontPreview, setFrontPreview] = useState<string | null>(null);
  const [backFile, setBackFile] = useState<File | null>(null);
  const [backPreview, setBackPreview] = useState<string | null>(null);
  useEffect(() => () => { if (frontPreview) URL.revokeObjectURL(frontPreview); }, [frontPreview]);
  useEffect(() => () => { if (backPreview) URL.revokeObjectURL(backPreview); }, [backPreview]);

  // Form Fields
  const [fullName, setFullName] = useState('');
  const [nicNumber, setNicNumber] = useState('');
  const [dob, setDob] = useState('');

  // Processing state
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<VerificationResponse | null>(null);

  // Backend status
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [backendMeta, setBackendMeta] = useState<any>(null);

  useEffect(() => {
    checkBackendHealth()
      .then((data) => {
        setBackendStatus('online');
        setBackendMeta(data);
      })
      .catch(() => {
        setBackendStatus('offline');
      });
  }, []);

  const handleFrontSelect = (file: File | null) => {
    setFrontFile(file);
    if (file) {
      setFrontPreview(URL.createObjectURL(file));
    } else {
      setFrontPreview(null);
    }
  };

  const handleBackSelect = (file: File | null) => {
    setBackFile(file);
    if (file) {
      setBackPreview(URL.createObjectURL(file));
    } else {
      setBackPreview(null);
    }
  };

  const handleReset = () => {
    setFrontFile(null);
    setFrontPreview(null);
    setBackFile(null);
    setBackPreview(null);
    setFullName('');
    setNicNumber('');
    setDob('');
    setResult(null);
    setErrorMsg(null);
  };

  // Synthetic Test Presets for Quick Testing
  const handleLoadPreset = (type: 'old' | 'smart') => {
    if (type === 'old') {
      setFullName('K. A. Perera');
      setNicNumber('853451234V');
      setDob('1985-12-11');
    } else if (type === 'smart') {
      setFullName('Nimal Silva');
      setNicNumber('199518001234');
      setDob('1995-06-29');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!frontFile) {
      setErrorMsg('Please select or upload a front document image of the NIC.');
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);

    const formData = new FormData();
    formData.append('front_image', frontFile);
    if (backFile) {
      formData.append('back_image', backFile);
    }
    if (fullName.trim()) formData.append('full_name', fullName.trim());
    if (nicNumber.trim()) formData.append('nic_number', nicNumber.trim());
    if (dob.trim()) formData.append('dob', dob.trim());

    try {
      const response = await verifyNICDocument(formData);
      setResult(response);
    } catch (err: any) {
      setErrorMsg(err.message || 'An error occurred during verification processing.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleApplyExtractedToForm = (nic: string, name: string, birthDate: string) => {
    if (nic) setNicNumber(nic);
    if (name) setFullName(name);
    if (birthDate) setDob(birthDate);
    setResult(null); // Return to form with values filled
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Top Disclaimer Bar */}
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-3 px-4 flex items-center justify-between text-xs text-amber-900 font-medium">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
          <span>
            <strong>Experimental PoC:</strong> Strictly for document detection & OCR testing. Not a production identity verification system.
          </span>
        </div>
        <DisclaimerModal />
      </div>

      {/* Main Header */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-sl-maroon inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-sl-gold inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-sl-orange inline-block" />
            <span>Sri Lanka National Identity Card Verifier</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight">
            NIC Document Detection & OCR Testing
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Multi-generation Sri Lankan NIC validation, image quality checks, and heuristic field matching.
          </p>
        </div>

        {/* Backend health status badge */}
        <div className="flex items-center gap-2 self-start md:self-auto bg-white px-3.5 py-2 rounded-xl border border-slate-200 shadow-2xs text-xs">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              backendStatus === 'online'
                ? 'bg-emerald-500 animate-pulse'
                : backendStatus === 'checking'
                ? 'bg-amber-400'
                : 'bg-rose-500'
            }`}
          />
          <span className="font-semibold text-slate-700">
            Backend API:{' '}
            <span className="font-normal text-slate-500">
              {backendStatus === 'online'
                ? `Online (${backendMeta?.ocr_engine || 'Local'})`
                : backendStatus === 'checking'
                ? 'Checking...'
                : 'Offline (Start FastAPI at :8000)'}
            </span>
          </span>
        </div>
      </header>

      {/* Results View or Form View */}
      {result ? (
        <ResultsView
          result={result}
          frontPreview={frontPreview}
          backPreview={backPreview}
          onReset={handleReset}
          onApplyExtractedToForm={handleApplyExtractedToForm}
        />
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Quick preset buttons for convenience */}
          <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-white/70 border border-slate-200/80 rounded-2xl text-xs">
            <span className="text-slate-600 font-medium flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-amber-500" />
              Quick Form Test Presets:
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleLoadPreset('old')}
                className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-700 font-medium transition"
              >
                Old 9-Digit (853451234V)
              </button>
              <button
                type="button"
                onClick={() => handleLoadPreset('smart')}
                className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-700 font-medium transition"
              >
                New 12-Digit (199518001234)
              </button>
              <button
                type="button"
                onClick={handleReset}
                className="px-2 py-1 text-slate-400 hover:text-slate-600 transition"
              >
                Clear
              </button>
            </div>
          </div>

          {/* Grid Layout: Uploaders on Left, Form on Right */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Image Upload Column (7 cols on lg) */}
            <div className="lg:col-span-7 bg-white/80 backdrop-blur rounded-2xl p-5 border border-slate-200/80 shadow-sm space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <h3 className="font-semibold text-slate-800 text-sm flex items-center gap-2">
                  <UploadCloud className="w-4 h-4 text-slate-500" />
                  Document Photos
                </h3>
                <span className="text-[11px] text-slate-500">
                  Evaluated for blur, glare, and cropping
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <ImageUploader
                  label="NIC Front Image"
                  description="Front side showing photo, NIC number & name"
                  required
                  file={frontFile}
                  previewUrl={frontPreview}
                  onFileSelect={handleFrontSelect}
                />
                <ImageUploader
                  label="NIC Back Image (Optional)"
                  description="Show the entire back, including the barcode if present"
                  file={backFile}
                  previewUrl={backPreview}
                  onFileSelect={handleBackSelect}
                />
              </div>

              <p className="text-xs text-slate-600">
                For a modern NIC, keep the full barcode in focus and free of glare.
                The verifier scans it automatically when you include the back photo.
              </p>

              <div className="p-3 bg-slate-50 rounded-xl text-[11px] text-slate-500 space-y-1">
                <p className="font-semibold text-slate-700">Photo Capture Advice:</p>
                <p>• Lay card flat on a plain, dark background.</p>
                <p>• Avoid camera flash reflections and hold phone steady to prevent blur.</p>
                <p>• Synthetic test card samples are provided in <code>backend/samples/</code>.</p>
              </div>
            </div>

            {/* Owner Info Form Column (5 cols on lg) */}
            <div className="lg:col-span-5">
              <OwnerForm
                fullName={fullName}
                nicNumber={nicNumber}
                dob={dob}
                onFullNameChange={setFullName}
                onNicNumberChange={setNicNumber}
                onDobChange={setDob}
                onAutoFillDob={(val) => setDob(val)}
              />
            </div>
          </div>

          {/* Error Message Display */}
          {errorMsg && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Action Footer */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-200">
            <p className="text-xs text-slate-500">
              Ephemeral in-memory processing. Images are never stored or logged.
            </p>

            <div className="flex items-center gap-3 w-full sm:w-auto">
              <button
                type="button"
                onClick={handleReset}
                disabled={isLoading}
                className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-100 font-medium text-xs transition disabled:opacity-50"
              >
                Reset
              </button>

              <button
                type="submit"
                disabled={isLoading || !frontFile}
                className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold text-xs transition shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>{backFile ? 'Reading card and scanning barcode…' : 'Reading front photo…'}</span>
                  </>
                ) : (
                  <>
                    <FileCheck className="w-4 h-4" />
                    <span>{backFile ? 'Read NIC and scan barcode' : 'Read NIC'}</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Footer */}
      <footer className="pt-8 pb-4 border-t border-slate-200/80 text-center text-xs text-slate-400 space-y-2">
        <p>
          Sri Lankan NIC Document Detection & OCR Testing • Proof of Concept • Localhost Only
        </p>
        <p className="text-[11px] text-slate-400">
          Local Windows OCR and image analysis • Final identity determination requires authorized manual review.
        </p>
      </footer>
    </div>
  );
}
