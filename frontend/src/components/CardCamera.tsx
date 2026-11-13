'use client';

import { useEffect, useRef, useState } from 'react';

export function CardCamera({ onCapture, onClose }: { onCapture: (file: File) => void; onClose: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    let stream: MediaStream | undefined;
    async function start() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 } },
          audio: false,
        });
        if (!active || !video.current) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        video.current.srcObject = stream;
      } catch {
        if (active) setError('Camera unavailable. Check permission or choose an existing photo.');
      }
    }
    void start();
    return () => {
      active = false;
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  function capture() {
    const source = video.current;
    if (!source?.videoWidth) return;
    const canvas = document.createElement('canvas');
    canvas.width = source.videoWidth;
    canvas.height = source.videoHeight;
    const context = canvas.getContext('2d');
    if (!context) return;
    context.drawImage(source, 0, 0);
    canvas.toBlob((blob) => {
      if (blob && video.current) onCapture(new File([blob], 'nic-camera.jpg', { type: blob.type }));
    }, 'image/jpeg', .96);
  }

  return (
    <div className="space-y-2">
      {error ? <p role="alert" className="text-sm text-rose-700">{error}</p> : (
        <>
          <p className="text-xs text-slate-600">Keep all four corners inside the guide. Turn off flash and hold the camera steady.</p>
          <div className="relative grid place-items-center overflow-hidden rounded-xl bg-slate-900">
            <video ref={video} onCanPlay={() => setReady(true)} autoPlay playsInline muted className="block w-full" />
            <div aria-hidden="true" className="pointer-events-none absolute w-3/4 max-h-[85%] aspect-[1.58] rounded-lg border-2 border-white shadow-[0_0_0_100vmax_#0005]" />
          </div>
        </>
      )}
      <button type="button" disabled={!ready} onClick={capture} className="mr-3 rounded-lg bg-slate-900 px-3 py-2 text-xs text-white disabled:opacity-40">Take photo</button>
      <button type="button" onClick={onClose} className="text-xs underline">Close camera</button>
    </div>
  );
}
