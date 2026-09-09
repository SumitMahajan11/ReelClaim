import React, { useState, useEffect } from 'react';
import { Search, Loader2, AlertCircle, Link as LinkIcon, FileText, Info, Key, Video } from 'lucide-react';
import { ProgressStep } from '@/lib/types';

const YoutubeIcon: React.FC<{ className?: string }> = ({ className = "w-4 h-4" }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
  </svg>
);

export interface AuditFormSubmitParams {
  caption?: string;
  videoUrl?: string;
  overrideUrl?: string;
  apiKey?: string;
  youtubeApiKey?: string;
}

interface AuditFormProps {
  onSubmit: (params: AuditFormSubmitParams) => void;
  isLoading: boolean;
  currentStep: ProgressStep;
  retryDetails?: { retryAttempt?: number; maxRetries?: number; nextDelaySec?: number } | null;
  error: string | null;
}

const PRESET_EXAMPLES = [
  {
    platform: 'youtube' as const,
    label: 'YouTube Short: Boot.dev Review',
    videoUrl: 'https://youtube.com/shorts/3f5G8kL9XYZ',
    overrideUrl: 'https://boot.dev/pricing',
    caption: 'Boot.dev monthly coding subscription and 30-day refund guarantee review.'
  },
  {
    platform: 'youtube' as const,
    label: 'YouTube Short: Vercel Free Tier',
    videoUrl: 'https://youtube.com/shorts/vercelHobbyTier',
    overrideUrl: 'https://vercel.com/pricing',
    caption: 'Vercel Hobby plan is 100% free forever for personal projects with zero monthly fees.'
  },
  {
    platform: 'instagram' as const,
    label: 'IG Reel: GitHub Actions (Partial)',
    caption: 'GitHub Free plan includes unlimited public/private repositories with 2,000 Action automation minutes per month!',
    overrideUrl: 'https://github.com/pricing',
    videoUrl: ''
  },
  {
    platform: 'instagram' as const,
    label: 'IG Reel: Codecademy 7-Day Trial',
    caption: 'Codecademy Pro membership gives access to all skill paths with a 7-day free trial included!',
    overrideUrl: 'https://www.codecademy.com/pricing',
    videoUrl: ''
  },
  {
    platform: 'instagram' as const,
    label: 'IG Reel: Planted False Guarantee',
    caption: '100% Free Full-Stack Web Development Bootcamp with no fees ever! Also no refunds provided under any circumstances.',
    overrideUrl: 'https://boot.dev/pricing',
    videoUrl: ''
  }
];

export const AuditForm: React.FC<AuditFormProps> = ({ onSubmit, isLoading, currentStep, retryDetails, error }) => {
  const [platform, setPlatform] = useState<'youtube' | 'instagram'>('youtube');
  const [videoUrl, setVideoUrl] = useState<string>('');
  const [caption, setCaption] = useState<string>('');
  const [url, setUrl] = useState<string>('');
  const [apiKey, setApiKey] = useState<string>('');
  const [youtubeApiKey, setYoutubeApiKey] = useState<string>('');
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);

  // Timer for smooth rotating progress status & cold-start notice
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isLoading) {
      setElapsedSeconds(0);
      interval = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      setElapsedSeconds(0);
    }
    return () => clearInterval(interval);
  }, [isLoading]);

  // Dynamic rotating status message based on measured timings
  const getStatusMessage = (): string => {
    if (currentStep === 'crawling_busy') {
      return `Server busy — retrying (attempt ${retryDetails?.retryAttempt || 1} of ${retryDetails?.maxRetries || 4}) in ${retryDetails?.nextDelaySec || 3}s...`;
    }

    if (platform === 'youtube' && elapsedSeconds < 3) {
      return 'Fetching YouTube video metadata & audio captions...';
    } else if (elapsedSeconds < 6) {
      return 'Extracting claims from transcript & caption...';
    } else if (elapsedSeconds < 14) {
      return 'Gathering multi-source evidence (Site, Search, Wayback, WHOIS)...';
    } else if (elapsedSeconds < 24) {
      return 'Cross-checking claims with Gemini Consensus Engine...';
    } else {
      return 'Finalizing claim verification report...';
    }
  };

  const handleVideoUrlChange = (val: string) => {
    setVideoUrl(val);
    setValidationError(null);
    if (val.includes('instagram.com') && platform === 'youtube') {
      setPlatform('instagram');
    }
  };

  const handleCaptionChange = (val: string) => {
    setCaption(val);
    setValidationError(null);
    if ((val.includes('youtube.com/shorts') || val.includes('youtu.be/')) && platform === 'instagram') {
      // Auto-switch to YouTube if user pasted a YouTube link in caption
      const match = val.match(/https?:\/\/(?:www\.)?(?:youtube\.com\/shorts\/|youtu\.be\/)[^\s]+/);
      if (match) {
        setVideoUrl(match[0]);
        setPlatform('youtube');
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (platform === 'youtube') {
      if (!videoUrl.trim()) {
        setValidationError('Please enter a valid YouTube Shorts or Video URL.');
        return;
      }
      try {
        new URL(videoUrl.startsWith('http') ? videoUrl : `https://${videoUrl}`);
      } catch {
        setValidationError('Please enter a valid YouTube URL (e.g., https://youtube.com/shorts/...).');
        return;
      }
      onSubmit({
        videoUrl: videoUrl.trim(),
        overrideUrl: url.trim() || undefined,
        apiKey: apiKey.trim() || undefined,
        youtubeApiKey: youtubeApiKey.trim() || undefined
      });
    } else {
      if (!caption.trim()) {
        setValidationError('Please paste or enter the social media reel caption/claim text.');
        return;
      }
      if (url.trim()) {
        try {
          new URL(url.startsWith('http') ? url : `https://${url}`);
        } catch {
          setValidationError('Please enter a valid site URL (e.g., https://example.com).');
          return;
        }
      }
      onSubmit({
        caption: caption.trim(),
        overrideUrl: url.trim() || undefined,
        apiKey: apiKey.trim() || undefined,
        youtubeApiKey: youtubeApiKey.trim() || undefined
      });
    }
  };

  const handlePresetSelect = (preset: typeof PRESET_EXAMPLES[0]) => {
    setPlatform(preset.platform);
    if (preset.platform === 'youtube') {
      setVideoUrl(preset.videoUrl);
      setUrl(preset.overrideUrl);
      setCaption('');
    } else {
      setCaption(preset.caption);
      setUrl(preset.overrideUrl);
      setVideoUrl('');
    }
    setValidationError(null);
  };

  const getStepStatusStyle = (step: 'extracting' | 'crawling' | 'cross_checking'): React.CSSProperties => {
    if (currentStep === step || (step === 'crawling' && currentStep === 'crawling_busy')) {
      return {
        backgroundColor: 'var(--bg-elevated)',
        borderColor: 'var(--border-bright)',
        color: 'var(--text-primary)',
        fontWeight: '600',
      };
    }
    const steps: Array<'extracting' | 'crawling' | 'cross_checking'> = ['extracting', 'crawling', 'cross_checking'];
    const currentIndex = steps.indexOf(currentStep === 'crawling_busy' ? 'crawling' : (currentStep as any));
    const stepIndex = steps.indexOf(step);
    if (stepIndex < currentIndex) {
      return {
        backgroundColor: 'var(--verdict-verified-bg)',
        borderColor: 'var(--verdict-verified-border)',
        color: 'var(--verdict-verified-text)',
      };
    }
    return {
      backgroundColor: 'var(--bg-card-subtle)',
      borderColor: 'var(--border-subtle)',
      color: 'var(--text-muted)',
    };
  };

  return (
    <div className="w-full space-y-6">
      {/* Header Info */}
      <div className="space-y-2">
        <span
          className="text-[10px] uppercase tracking-widest font-semibold"
          style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.12em' }}
        >
          Claim Intake & Verification
        </span>
        <h2
          className="text-lg font-bold tracking-tight leading-snug"
          style={{ fontFamily: 'var(--font-serif)', color: 'var(--text-primary)' }}
        >
          Audit Claims Against Multi-Source Evidence
        </h2>
        <p className="text-xs leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
          Verify promotional claims from YouTube Shorts and Instagram Reels against site terms, independent reviews, Wayback history, and WHOIS domain age.
        </p>
      </div>

      {/* Platform Selector Tabs */}
      <div className="grid grid-cols-2 p-1 rounded-xl border gap-1" style={{ backgroundColor: 'var(--bg-card-subtle)', borderColor: 'var(--border-med)' }}>
        <button
          type="button"
          onClick={() => setPlatform('youtube')}
          className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold cursor-pointer transition-all ${
            platform === 'youtube' ? 'shadow-sm' : 'opacity-70 hover:opacity-100'
          }`}
          style={{
            backgroundColor: platform === 'youtube' ? 'var(--bg-elevated)' : 'transparent',
            color: platform === 'youtube' ? 'var(--text-primary)' : 'var(--text-muted)',
            border: platform === 'youtube' ? '1px solid var(--border-bright)' : '1px solid transparent',
          }}
        >
          <YoutubeIcon className="w-4 h-4 text-red-500" />
          <span>YouTube Shorts</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-red-950/60 text-red-300 border border-red-800/60">
            AUTO
          </span>
        </button>

        <button
          type="button"
          onClick={() => setPlatform('instagram')}
          className={`flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-semibold cursor-pointer transition-all ${
            platform === 'instagram' ? 'shadow-sm' : 'opacity-70 hover:opacity-100'
          }`}
          style={{
            backgroundColor: platform === 'instagram' ? 'var(--bg-elevated)' : 'transparent',
            color: platform === 'instagram' ? 'var(--text-primary)' : 'var(--text-muted)',
            border: platform === 'instagram' ? '1px solid var(--border-bright)' : '1px solid transparent',
          }}
        >
          <FileText className="w-3.5 h-3.5 text-purple-400" />
          <span>Instagram Reels</span>
          <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-purple-950/60 text-purple-300 border border-purple-800/60">
            MANUAL
          </span>
        </button>
      </div>

      {/* Preset Demo Options */}
      <div className="space-y-2">
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Try Demo Scenarios:</span>
        <div className="flex flex-wrap gap-1.5">
          {PRESET_EXAMPLES.map((preset, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handlePresetSelect(preset)}
              disabled={isLoading}
              className="text-[11px] px-2.5 py-1 rounded-lg border transition-all cursor-pointer disabled:opacity-50 hover:opacity-80 flex items-center gap-1.5"
              style={{
                backgroundColor: 'var(--bg-card-subtle)',
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-primary)',
              }}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${preset.platform === 'youtube' ? 'bg-red-400' : 'bg-purple-400'}`} />
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* YouTube Ingest Path */}
        {platform === 'youtube' ? (
          <div className="space-y-3">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                  <LinkIcon className="w-3.5 h-3.5 text-red-400" />
                  YouTube Short / Video URL <span className="text-rose-500">*</span>
                </label>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-1.5 py-0.5 rounded">
                  URL-Only Ingest
                </span>
              </div>
              <input
                type="text"
                value={videoUrl}
                onChange={(e) => handleVideoUrlChange(e.target.value)}
                disabled={isLoading}
                placeholder="https://youtube.com/shorts/dQw4w9WgXcQ or https://youtu.be/..."
                className="w-full px-3 py-2.5 border rounded-xl text-xs font-mono transition-all focus:outline-none focus:ring-2"
                style={{
                  backgroundColor: 'var(--bg-card-subtle)',
                  borderColor: 'var(--border-med)',
                  color: 'var(--text-primary)',
                }}
              />
            </div>

            {/* Explanatory Notice for YouTube Auto-Ingest */}
            <div className="p-3 rounded-lg border text-[11px] leading-relaxed space-y-1" style={{ backgroundColor: 'var(--bg)', borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}>
              <div className="flex items-start gap-1.5">
                <span className="font-semibold text-emerald-400">✓ Auto-Ingest Active:</span>
                <span>
                  ReelClaim connects to the official YouTube API and transcript engine to automatically extract the video title, description, and audio captions.
                </span>
              </div>
            </div>

            {/* Optional Promoted URL Override */}
            <div className="space-y-1.5">
              <label className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                <LinkIcon className="w-3.5 h-3.5" style={{ color: 'var(--text-accent)' }} />
                Promoted Landing Page URL <span className="text-[10px] font-normal" style={{ color: 'var(--text-muted)' }}>(Optional override if not in video description)</span>
              </label>
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={isLoading}
                placeholder="https://boot.dev/pricing"
                className="w-full px-3 py-2 border rounded-xl text-xs transition-all focus:outline-none focus:ring-2"
                style={{
                  backgroundColor: 'var(--bg-card-subtle)',
                  borderColor: 'var(--border-med)',
                  color: 'var(--text-primary)',
                }}
              />
            </div>
          </div>
        ) : (
          /* Instagram Manual Caption Path */
          <div className="space-y-3">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                  <FileText className="w-3.5 h-3.5 text-purple-400" />
                  Instagram Reel Caption & Claims <span className="text-rose-500">*</span>
                </label>
                <span className="text-[10px] font-mono text-purple-300 bg-purple-950/40 border border-purple-800/40 px-1.5 py-0.5 rounded">
                  Manual Text Paste
                </span>
              </div>
              <textarea
                rows={4}
                value={caption}
                onChange={(e) => handleCaptionChange(e.target.value)}
                disabled={isLoading}
                placeholder="Paste Instagram reel caption, promotional copy, or spoken claims..."
                className="w-full px-3 py-2.5 border rounded-xl text-xs transition-all resize-y focus:outline-none focus:ring-2"
                style={{
                  backgroundColor: 'var(--bg-card-subtle)',
                  borderColor: 'var(--border-med)',
                  color: 'var(--text-primary)',
                }}
              />
            </div>

            {/* Explanatory Notice for Instagram Policy */}
            <div className="p-3 rounded-lg border text-[11px] leading-relaxed space-y-1" style={{ backgroundColor: 'var(--bg)', borderColor: 'var(--border-subtle)', color: 'var(--text-secondary)' }}>
              <div className="flex items-start gap-1.5">
                <span className="font-semibold text-purple-300">ℹ Instagram Policy Notice:</span>
                <span>
                  Instagram Graph API requires complex App Review for public caption scraping. Paste the caption text from the reel to check against published site evidence.
                </span>
              </div>
            </div>

            {/* URL Input */}
            <div className="space-y-1.5">
              <label className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                <LinkIcon className="w-3.5 h-3.5" style={{ color: 'var(--text-accent)' }} />
                Promoted Site URL <span className="text-[10px] font-normal" style={{ color: 'var(--text-muted)' }}>(Optional override if not in caption)</span>
              </label>
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={isLoading}
                placeholder="https://boot.dev/pricing"
                className="w-full px-3 py-2 border rounded-xl text-xs transition-all focus:outline-none focus:ring-2"
                style={{
                  backgroundColor: 'var(--bg-card-subtle)',
                  borderColor: 'var(--border-med)',
                  color: 'var(--text-primary)',
                }}
              />
            </div>
          </div>
        )}

        {/* Collapsible BYOK Section */}
        <div className="space-y-2 pt-1 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-1.5 text-xs font-semibold cursor-pointer hover:opacity-80 transition-opacity"
            style={{ color: 'var(--text-secondary)' }}
          >
            <Key className="w-3.5 h-3.5" style={{ color: 'var(--text-accent)' }} />
            <span>Custom API Keys (BYOK)</span>
            <span className="text-[10px] font-normal" style={{ color: 'var(--text-muted)' }}>
              {showAdvanced ? '▲ hide' : '▼ optional'}
            </span>
          </button>

          {showAdvanced && (
            <div className="p-3 rounded-xl border space-y-3 animate-fadeIn" style={{ backgroundColor: 'var(--bg-card-subtle)', borderColor: 'var(--border-med)' }}>
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                  Google Gemini API Key
                </label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  disabled={isLoading}
                  placeholder="AIzaSy..."
                  className="w-full px-3 py-2 border rounded-xl text-xs font-mono transition-all focus:outline-none focus:ring-2"
                  style={{
                    backgroundColor: 'var(--bg)',
                    borderColor: 'var(--border-med)',
                    color: 'var(--text-primary)',
                  }}
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>
                  YouTube Data API v3 Key <span className="text-[10px] font-normal text-muted">(Optional for direct YouTube quota)</span>
                </label>
                <input
                  type="password"
                  value={youtubeApiKey}
                  onChange={(e) => setYoutubeApiKey(e.target.value)}
                  disabled={isLoading}
                  placeholder="AIzaSy..."
                  className="w-full px-3 py-2 border rounded-xl text-xs font-mono transition-all focus:outline-none focus:ring-2"
                  style={{
                    backgroundColor: 'var(--bg)',
                    borderColor: 'var(--border-med)',
                    color: 'var(--text-primary)',
                  }}
                />
              </div>

              <div className="flex items-start gap-1.5 text-[11px] leading-snug" style={{ color: 'var(--text-muted)' }}>
                <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" style={{ color: 'var(--text-accent)' }} />
                <span>
                  Keys are used in-memory for this audit session only and are never saved to disk.
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Validation or Error Message */}
        {(validationError || error) && (
          <div className="flex items-center gap-2.5 p-3.5 rounded-xl bg-rose-950/40 border border-rose-900/60 text-rose-300 text-sm">
            <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <span>{validationError || error}</span>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isLoading}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-5 font-semibold text-xs rounded cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-85"
          style={{
            backgroundColor: 'var(--accent-brand)',
            color: 'var(--bg)',
            fontFamily: 'var(--font-mono)',
            letterSpacing: '0.04em',
            border: 'none',
          }}
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>
                {currentStep === 'crawling_busy'
                  ? `Retrying (${retryDetails?.retryAttempt || 1}/${retryDetails?.maxRetries || 4})...`
                  : getStatusMessage()}
              </span>
            </>
          ) : (
            <>
              <Search className="w-3.5 h-3.5" />
              <span>{platform === 'youtube' ? 'Audit YouTube Short →' : 'Audit Instagram Reel →'}</span>
            </>
          )}
        </button>
      </form>

      {/* Multi-step Live Loading Progress */}
      {isLoading && (
        <div
          className="p-4 rounded-xl border space-y-3.5 animate-fadeIn"
          style={{
            backgroundColor: 'var(--bg-card-subtle)',
            borderColor: 'var(--border-med)',
          }}
        >
          <div className="flex items-center justify-between text-xs font-medium" style={{ color: 'var(--text-muted)' }}>
            <span className="uppercase tracking-wider text-[10px]">Pipeline Progress</span>
            <span className="text-xs font-semibold flex items-center gap-1.5" style={{ color: 'var(--text-accent)' }}>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {getStatusMessage()}
            </span>
          </div>

          <div
            className="w-full h-1.5 overflow-hidden"
            style={{
              backgroundColor: 'var(--bg-elevated)',
              borderRadius: '2px',
            }}
          >
            <div
              className="h-full"
              style={{
                width: `${Math.min(95, Math.max(8, elapsedSeconds * 4))}%`,
                backgroundColor: 'var(--accent-brand)',
                transition: 'width 0.5s ease-out',
                borderRadius: '2px',
              }}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-1.5 text-[11px]">
            <div className="p-2 rounded border text-center" style={getStepStatusStyle('extracting')}>
              1. Ingest & Claims
            </div>
            <div className="p-2 rounded border text-center" style={getStepStatusStyle('crawling')}>
              {currentStep === 'crawling_busy'
                ? `2. Busy (${retryDetails?.retryAttempt}/${retryDetails?.maxRetries})`
                : '2. Multi-Evidence'}
            </div>
            <div className="p-2 rounded border text-center" style={getStepStatusStyle('cross_checking')}>
              3. Checking & Verdict
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
