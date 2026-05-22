import { useRef, useCallback, useEffect, MutableRefObject } from 'react';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  emoji: string;
  life: number;
  decay: number;
  size: number;
  rotation: number;
  rotationSpeed: number;
}

export interface UseParticleSystemReturn {
  emit: (x: number, y: number, emoji: string, count?: number) => void;
  emitBurst: (x: number, y: number, emoji: string) => void;
  start: () => void;
  stop: () => void;
  destroy: () => void;
}

export function useParticleSystem(
  externalRef?: MutableRefObject<HTMLCanvasElement | null>
): UseParticleSystemReturn {
  const internalRef = useRef<HTMLCanvasElement>(null);
  const canvasRef = externalRef || internalRef;
  const particlesRef = useRef<Particle[]>([]);
  const rafRef = useRef<number | undefined>(undefined);
  const isRunningRef = useRef(false);

  const update = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    particlesRef.current = particlesRef.current.filter((p) => {
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.05;
      p.life -= p.decay;
      p.rotation += p.rotationSpeed;

      if (p.life > 0) {
        ctx.save();
        ctx.globalAlpha = Math.max(0, p.life);
        ctx.font = `${p.size}px Arial`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rotation);
        ctx.fillText(p.emoji, 0, 0);
        ctx.restore();
        return true;
      }

      return false;
    });

    if (particlesRef.current.length > 0) {
      rafRef.current = requestAnimationFrame(update);
    } else {
      isRunningRef.current = false;
    }
  }, []);

  const start = useCallback(() => {
    if (isRunningRef.current) return;
    isRunningRef.current = true;
    rafRef.current = requestAnimationFrame(update);
  }, [update]);

  const stop = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = undefined;
    }
    isRunningRef.current = false;
  }, []);

  const emit = useCallback(
    (x: number, y: number, emoji: string, count: number = 8) => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      for (let i = 0; i < count; i++) {
        const angle = (i / count) * Math.PI * 2 + Math.random() * 0.5;
        const speed = 2 + Math.random() * 3;
        particlesRef.current.push({
          x,
          y,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed - 2,
          emoji,
          life: 1,
          decay: 0.015 + Math.random() * 0.01,
          size: 16 + Math.random() * 12,
          rotation: 0,
          rotationSpeed: (Math.random() - 0.5) * 0.2,
        });
      }

      if (!isRunningRef.current) {
        start();
      }
    },
    [start]
  );

  const emitBurst = useCallback(
    (x: number, y: number, emoji: string) => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;

      for (let i = 0; i < 16; i++) {
        const angle = (i / 16) * Math.PI * 2;
        const speed = 3 + Math.random() * 4;
        particlesRef.current.push({
          x: centerX,
          y: centerY,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          emoji,
          life: 1,
          decay: 0.02,
          size: 20 + Math.random() * 10,
          rotation: 0,
          rotationSpeed: (Math.random() - 0.5) * 0.3,
        });
      }

      emit(x, y, emoji, 8);

      if (!isRunningRef.current) {
        start();
      }
    },
    [emit, start]
  );

  const destroy = useCallback(() => {
    stop();
    particlesRef.current = [];
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (ctx && canvas) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }, [stop]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (rect) {
        canvas.width = rect.width;
        canvas.height = rect.height;
      }
    };

    resize();
    window.addEventListener('resize', resize);

    return () => {
      window.removeEventListener('resize', resize);
      destroy();
    };
  }, [destroy]);

  return {
    emit,
    emitBurst,
    start,
    stop,
    destroy,
  };
}