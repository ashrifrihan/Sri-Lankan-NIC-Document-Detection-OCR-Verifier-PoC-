'use client';
import React, { useRef, useState } from 'react';
import { UploadCloud, Trash2, CheckCircle2 } from 'lucide-react';
import { CardCamera } from './CardCamera';

interface ImageUploaderProps {
  label: string;
  description: string;
  required?: boolean;
  file: File | null;
  previewUrl: string | null;
  onFileSelect: (file: File | null) => void;
}

export const ImageUploader: React.FC<ImageUploaderProps> = ({
  label,
  description,
  required = false,
  file,
  previewUrl,
  onFileSelect,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const selection = useRef(0);
  const [notice, setNotice] = useState('');
  const [rotating, setRotating] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [crop, setCrop] = useState<number[] | null>(null);
  const [cropping, setCropping] = useState(false);

  const selectImage = async (selected: File) => {
    const attempt = ++selection.current;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(selected.type) ||
        selected.size === 0 || selected.size > 10 * 1024 * 1024) {
      setNotice('Choose a JPEG, PNG, or WebP image up to 10 MB.');
      return;
    }
    try {
      const image = await createImageBitmap(selected);
      try {
        if (attempt !== selection.current) return;
        const short = Math.min(image.width, image.height);
        const long = Math.max(image.width, image.height);
        let hint = '';
        if (short < 500 || long < 800) {
          hint = 'This photo is small. Move closer and keep all four card corners visible.';
        } else {
          const canvas = document.createElement('canvas');
          canvas.width = Math.max(1, Math.round(160 * image.width / long));
          canvas.height = Math.max(1, Math.round(160 * image.height / long));
          const context = canvas.getContext('2d');
          if (context) {
            context.drawImage(image, 0, 0, canvas.width, canvas.height);
            const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
            let brightness = 0;
            let highlights = 0;
            for (let pixel = 0; pixel < data.length; pixel += 4) {
              const light = .2126 * data[pixel] + .7152 * data[pixel + 1] + .0722 * data[pixel + 2];
              brightness += light;
              if (light > 249) highlights++;
            }
            if (brightness / (data.length / 4) < 45) hint = 'This photo looks dark. Retake it under even lighting.';
            else if (highlights / (data.length / 4) > .2) hint = 'This photo has very bright areas. Check that glare is not covering the text.';
            else {
              let detail = 0;
              const stride = canvas.width * 4;
              for (let y = 1; y < canvas.height - 1; y++) {
                for (let x = 1; x < canvas.width - 1; x++) {
                  const i = y * stride + x * 4;
                  const edge = 4 * data[i + 1] - data[i - 3] - data[i + 5] - data[i + 1 - stride] - data[i + 1 + stride];
                  detail += edge * edge;
                }
              }
              if (detail / (canvas.width * canvas.height) < 18) hint = 'This photo may be out of focus. Tap the card text to focus and retake it.';
            }
          }
        }
        setNotice(hint);
        setCrop(null);
        onFileSelect(selected);
      } finally {
        image.close();
      }
    } catch {
      if (attempt === selection.current) setNotice('This image could not be opened. Choose another photo.');
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const selected = e.dataTransfer.files[0];
      void selectImage(selected);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      void selectImage(e.target.files[0]);
      e.currentTarget.value = '';
    }
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    ++selection.current;
    setNotice('');
    setCrop(null);
    onFileSelect(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  const rotatePhoto = async () => {
    if (!file) return;
    const attempt = ++selection.current;
    setRotating(true);
    try {
      const image = await createImageBitmap(file);
      try {
        const canvas = document.createElement('canvas');
        canvas.width = image.height;
        canvas.height = image.width;
        const context = canvas.getContext('2d');
        if (!context) throw new Error();
        context.translate(canvas.width, 0);
        context.rotate(Math.PI / 2);
        context.drawImage(image, 0, 0);
        const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', .95));
        if (!blob) throw new Error();
        if (attempt === selection.current) {
          await selectImage(new File([blob], 'rotated-nic.jpg', { type: blob.type }));
        }
      } finally {
        image.close();
      }
    } catch {
      if (attempt === selection.current) setNotice('Could not rotate this photo.');
    } finally {
      setRotating(false);
    }
  };

  const applyCrop = async () => {
    if (!file || !crop) return;
    const attempt = ++selection.current;
    setCropping(true);
    try {
      const image = await createImageBitmap(file);
      try {
        const [top, right, bottom, left] = crop;
        const x = Math.round(image.width * left / 100);
        const y = Math.round(image.height * top / 100);
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(image.width * (100 - left - right) / 100);
        canvas.height = Math.round(image.height * (100 - top - bottom) / 100);
        const context = canvas.getContext('2d');
        if (!context) throw new Error();
        context.drawImage(image, x, y, canvas.width, canvas.height, 0, 0, canvas.width, canvas.height);
        const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', .96));
        if (!blob) throw new Error();
        if (attempt === selection.current) await selectImage(new File([blob], 'cropped-nic.jpg', { type: blob.type }));
      } finally {
        image.close();
      }
    } catch {
      if (attempt === selection.current) setNotice('Could not crop this photo.');
    } finally {
      setCropping(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-semibold text-slate-800 flex items-center gap-1.5">
          {label}
          {required && <span className="text-rose-500 font-bold">*</span>}
        </label>
        {file && (
          <span className="text-xs text-emerald-600 font-medium flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" /> Selected ({(file.size / (1024 * 1024)).toFixed(2)} MB)
          </span>
        )}
      </div>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-2xl p-4 transition-all cursor-pointer flex flex-col items-center justify-center text-center min-h-[170px] ${
          previewUrl
            ? 'border-emerald-300 bg-emerald-50/20'
            : 'border-slate-300 hover:border-slate-400 bg-white/60 hover:bg-slate-50/50'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={handleChange}
        />

        {previewUrl ? (
          <div className="relative w-full h-full flex flex-col items-center">
            <img
              src={previewUrl}
              alt={label}
              className="max-h-36 rounded-xl object-contain shadow-sm border border-slate-200"
            />
            <div className="flex items-center gap-2 mt-2">
              <span className="text-xs text-slate-600 font-medium truncate max-w-[200px]">
                {file?.name}
              </span>
              <button
                type="button"
                onClick={handleClear}
                className="p-1 rounded-lg bg-rose-50 text-rose-600 hover:bg-rose-100 transition"
                title="Remove image"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <div className="p-3 bg-slate-100 rounded-2xl text-slate-500">
              <UploadCloud className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-800">
                Click to browse or drag & drop
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">{description}</p>
            </div>
            <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
              JPG, PNG, WebP (Max 10MB)
            </span>
          </div>
        )}
      </div>
      {notice && <p role="status" className="text-xs text-amber-800">{notice}</p>}
      {cameraOpen ? <CardCamera onClose={() => setCameraOpen(false)} onCapture={(photo) => {
        setCameraOpen(false);
        void selectImage(photo);
      }} /> : <button type="button" onClick={() => setCameraOpen(true)} className="self-start text-xs underline">Use camera</button>}
      {file && <button type="button" disabled={rotating || cropping} onClick={() => void rotatePhoto()}
        className="self-start rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium">
        {rotating ? 'Rotating…' : 'Rotate photo 90°'}
      </button>}
      {file && previewUrl && (crop ? (
        <div className="space-y-2 rounded-lg border p-3">
          <div className="bg-slate-900">
            <img src={previewUrl} alt="Crop preview" className="block w-full"
              style={{ clipPath: `inset(${crop.map((edge) => edge + '%').join(' ')})` }} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            {['Top', 'Right', 'Bottom', 'Left'].map((edge, index) => (
              <label key={edge} className="text-xs">{edge} trim {crop[index]}%
                <input className="block w-full" type="range" min={0} max={45} value={crop[index]}
                  onChange={(event) => setCrop(crop.map((value, i) => i === index ? Number(event.target.value) : value))} />
              </label>
            ))}
          </div>
          <button type="button" disabled={cropping || rotating} onClick={() => void applyCrop()} className="mr-3 text-xs underline">Apply crop</button>
          <button type="button" disabled={cropping} onClick={() => setCrop(null)} className="text-xs underline">Cancel</button>
        </div>
      ) : <button type="button" onClick={() => setCrop([0, 0, 0, 0])} className="self-start text-xs underline">Crop photo</button>)}
    </div>
  );
};
