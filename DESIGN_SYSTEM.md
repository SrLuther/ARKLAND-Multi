# ARKLAND Design System v2.0
## Repaginação Visual Completa — Guia de Design Profissional

---

## 1. Filosofia de Design

### 1.1 Conceito
**"Command Center"** — Interface que evoca um centro de comando militar/futurista. O usuário é o operador de uma base de operação crítica. A estética transmite **controle, precisão e profissionalismo**, alinhada ao universo sci-fi do ARK: Survival Evolved.

### 1.2 Pilares de Design
| Pilar | Definição |
|-------|-----------|
| **Clareza** | Hierarquia visual forte, informações prioritárias em destaque |
| **Velocidade** | Interações instantâneas, feedback visual imediato |
| **Profundidade** | Camadas visuais com sombras e glassmorphism sutil |
| **Identidade** | Paleta escura premium com acentos neon/cyan (modo TEK) ou verde vibrante (modo PRIMITIVE) |

### 1.3 Inspirações Visuais
- **Ark Survival Evolved UI** — Brutalismo tático
- **Cyberpunk 2077** — Neon com elementos tecnológicos
- **Figma/Dashboards SaaS** — Layouts de controle modernos
- **Linear/Raycast** — Minimalismo de alta qualidade

---

## 2. Sistema de Cores

### 2.1 Paleta Base (Dark Theme)

```css
:root {
  /* ── Backgrounds ─────────────────────────────── */
  --bg-base:        #030712;   /* slate-950 — fundo raiz */
  --bg-surface:     #0a0f1c;   /* slate-975 — cards, modais */
  --bg-elevated:    #111827;   /* gray-900 — elementos elevados */
  --bg-overlay:     #1e293b;   /* slate-800 — hover states */
  
  /* ── Borda / Linhas ────────────────────────── */
  --border-subtle:  #0f172a;   /* Borda quase invisível */
  --border-default: #1e293b;   /* Borda padrão */
  --border-strong:  #334155;   /* Borda em foco */
  
  /* ── Texto ─────────────────────────────────── */
  --text-primary:   #f1f5f9;   /* slate-100 — título principal */
  --text-secondary: #94a3b8;   /* slate-400 — labels */
  --text-muted:     #64748b;   /* slate-500 — placeholders */
  --text-disabled:  #475569;   /* slate-600 — disabled */
  
  /* ── Acentos ───────────────────────────────── */
  --accent-cyan:    #06b6d4;   /* Modo TEK */
  --accent-green:   #22c55e;   /* Modo PRIMITIVE */
  --accent-purple:  #a855f7;   /* Híbrido/Especial */
  
  /* ── Status ────────────────────────────────── */
  --status-success: #22c55e;
  --status-warning: #f59e0b;
  --status-error:   #ef4444;
  --status-info:    #3b82f6;
}
```

### 2.2 Paleta Modo PRIMITIVE (Verde)

```css
:root[data-theme="primitive"] {
  /* Acento principal */
  --accent:         #22c55e;   /* emerald-500 */
  --accent-hover:   #16a34a;   /* emerald-600 */
  --accent-muted:   #052e16;   /* emerald-950 */
  --accent-subtle:  #14532d;   /* green-900 */
  
  /* Glow effect */
  --glow-primary:   0 0 20px rgba(34, 197, 94, 0.3);
  --glow-strong:    0 0 40px rgba(34, 197, 94, 0.5);
  
  /* Gradientes */
  --gradient-accent: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  --gradient-surface: linear-gradient(180deg, #0f172a 0%, #0a0f14 100%);
}
```

### 2.3 Paleta Modo TEK (Cyan)

```css
:root[data-theme="tek"] {
  /* Acento principal */
  --accent:         #06b6d4;   /* cyan-500 */
  --accent-hover:   #0891b2;   /* cyan-600 */
  --accent-muted:   #083344;   /* cyan-950 */
  --accent-subtle:  #164e63;   /* cyan-900 */
  
  /* Glow effect */
  --glow-primary:   0 0 20px rgba(6, 182, 212, 0.3);
  --glow-strong:    0 0 40px rgba(6, 182, 212, 0.5);
  
  /* Gradientes */
  --gradient-accent: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
  --gradient-surface: linear-gradient(180deg, #0f172a 0%, #0a0f1c 100%);
}
```

### 2.4 Status e Notificações

```css
:root {
  /* Status Colors */
  --server-stopped:  #6b7280;   /* gray-500 */
  --server-starting: #fbbf24;   /* amber-400 */
  --server-running:  #22c55e;   /* green-500 */
  --server-stopping: #fbbf24;   /* amber-400 */
  --server-crashed:  #ef4444;   /* red-500 */
  --server-updating: #f59e0b;   /* amber-500 */
  
  /* Badges */
  --badge-success-bg: rgba(34, 197, 94, 0.15);
  --badge-success-text: #22c55e;
  --badge-warning-bg: rgba(245, 158, 11, 0.15);
  --badge-warning-text: #f59e0b;
  --badge-error-bg: rgba(239, 68, 68, 0.15);
  --badge-error-text: #ef4444;
}
```

---

## 3. Tipografia

### 3.1 Família Tipográfica

```
┌─────────────────────────────────────────────────────────────┐
│ NÍVEL          │ FONTE                   │ USO              │
├─────────────────────────────────────────────────────────────┤
│ Display        │ Inter / Segoe UI Bold   │ Títulos de página │
│ Heading 1      │ Inter / Segoe UI SemBd  │ Seções principais│
│ Heading 2      │ Inter / Segoe UI SemBd  │ Subseções        │
│ Body           │ Inter / Segoe UI        │ Texto geral      │
│ Body Small     │ Inter / Segoe UI        │ Labels secundários│
│ Mono/Code      │ JetBrains Mono / Consolas│ Logs, IDs, cmds │
│ Badge          │ Inter / Segoe UI Medium │ Tags, badges     │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Escala Tipográfica

```css
:root {
  /* Display */
  --text-xs:    0.75rem;   /* 12px - badges, hints */
  --text-sm:    0.875rem;  /* 14px - labels secundários */
  --text-base:  1rem;      /* 16px - body text */
  --text-lg:    1.125rem;  /* 18px - labels de campo */
  --text-xl:    1.25rem;   /* 20px - títulos de seção */
  --text-2xl:   1.5rem;    /* 24px - títulos de card */
  --text-3xl:   1.875rem;  /* 30px - títulos de página */
  --text-4xl:   2.25rem;   /* 36px - display */
  
  /* Line Heights */
  --leading-tight:  1.25;
  --leading-normal: 1.5;
  --leading-relaxed: 1.75;
  
  /* Letter Spacing */
  --tracking-tight:  -0.025em;
  --tracking-normal:  0;
  --tracking-wide:    0.025em;
  --tracking-wider:   0.05em;
}
```

### 3.3 Hierarquia Visual

```
┌────────────────────────────────────────┐
│  TÍTULO DA PÁGINA          [actions]  │
│  Descrição contextual                 │
├────────────────────────────────────────┤
│                                        │
│  ┌──────────┐  ┌──────────┐           │
│  │ CARD     │  │ CARD     │           │
│  │ ───────  │  │ ───────  │           │
│  │ content  │  │ content  │           │
│  └──────────┘  └──────────┘           │
│                                        │
└────────────────────────────────────────┘

TÍTULO PÁGINA:   text-3xl, weight 700, text-primary
TÍTULO SEÇÃO:    text-xl,  weight 600, text-primary
TÍTULO CARD:    text-2xl, weight 600, text-primary
LABEL:          text-lg,  weight 500, text-secondary
BODY:           text-base, weight 400, text-primary
HINT:           text-sm,  weight 400, text-muted
CODE:           text-sm,  mono,    text-primary
```

---

## 4. Sistema Espacial

### 4.1 Grid Base (8px)

```css
:root {
  /* Espaçamento */
  --space-0:   0;
  --space-1:   4px;    /* 0.25rem */
  --space-2:   8px;    /* 0.5rem */
  --space-3:   12px;   /* 0.75rem */
  --space-4:   16px;   /* 1rem */
  --space-5:   20px;   /* 1.25rem */
  --space-6:   24px;   /* 1.5rem */
  --space-8:   32px;   /* 2rem */
  --space-10:  40px;   /* 2.5rem */
  --space-12:  48px;   /* 3rem */
  --space-16:  64px;   /* 4rem */
  
  /* Border Radius */
  --radius-sm:   4px;
  --radius-md:   8px;
  --radius-lg:   12px;
  --radius-xl:   16px;
  --radius-2xl:  24px;
  --radius-full: 9999px;
}
```

### 4.2 Layout da Aplicação

```
┌─────────────────────────────────────────────────────────────────┐
│  ┌─────────┬─────────────────────────────────────────┬───────┐ │
│  │         │  HEADER                                  │       │ │
│  │         │  ─────────────────────────────────────── │       │ │
│  │  SIDE   │                                          │ RIGHT │ │
│  │  BAR    │  CONTENT AREA                            │ PANEL │ │
│  │  72px   │                                          │ 280px │ │
│  │         │                                          │       │ │
│  │         │  ─────────────────────────────────────── │       │ │
│  │         │  FOOTER / STATUS BAR                     │       │ │
│  └─────────┴─────────────────────────────────────────┴───────┘ │
└─────────────────────────────────────────────────────────────────┘

SIDEBAR:  72px (collapsed) / 240px (expanded)
HEADER:   64px
RIGHT:    280px (optional panels)
FOOTER:   36px (status bar)
```

### 4.3 Cards e Containers

```css
/* Card Padrão */
.card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  transition: all 0.2s ease;
}

.card:hover {
  border-color: var(--accent);
  box-shadow: var(--glow-primary);
}

/* Card Elevado */
.card-elevated {
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3),
              0 2px 4px -2px rgba(0, 0, 0, 0.2);
}

/* Glassmorphism Card */
.card-glass {
  background: rgba(15, 23, 42, 0.7);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-xl);
}
```

---

## 5. Componentes Redesenhados

### 5.1 Botões

#### Botão Primário
```css
.btn-primary {
  /* Base */
  background: var(--gradient-accent);
  color: #ffffff;
  font-weight: 600;
  font-size: var(--text-sm);
  padding: var(--space-3) var(--space-6);
  border-radius: var(--radius-md);
  border: none;
  cursor: pointer;
  transition: all 0.15s ease;
  
  /* Hover */
  transform: translateY(-1px);
  box-shadow: var(--glow-primary);
  
  /* Active */
  transform: translateY(0);
  filter: brightness(0.95);
  
  /* Focus */
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}
```

#### Botão Secundário
```css
.btn-secondary {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-default);
  padding: var(--space-3) var(--space-6);
  border-radius: var(--radius-md);
  font-weight: 500;
  transition: all 0.15s ease;
}

.btn-secondary:hover {
  background: var(--bg-overlay);
  border-color: var(--border-strong);
  color: var(--text-primary);
}
```

#### Botão Danger
```css
.btn-danger {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
  padding: var(--space-3) var(--space-6);
  border-radius: var(--radius-md);
  font-weight: 500;
  transition: all 0.15s ease;
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: #ef4444;
}
```

#### Botão Icon-Only
```css
.btn-icon {
  width: 40px;
  height: 40px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-secondary);
  transition: all 0.15s ease;
}

.btn-icon:hover {
  background: var(--bg-overlay);
  border-color: var(--border-default);
  color: var(--text-primary);
}

.btn-icon.active {
  background: var(--accent-muted);
  color: var(--accent);
  border-color: var(--accent);
}
```

### 5.2 Inputs

#### Text Input
```css
.input {
  /* Base */
  background: var(--bg-base);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  color: var(--text-primary);
  font-size: var(--text-base);
  width: 100%;
  transition: all 0.15s ease;
}

.input::placeholder {
  color: var(--text-muted);
}

.input:hover {
  border-color: var(--border-strong);
}

.input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.1);
}

.input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Input com label */
.input-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.input-label {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
}

.input-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
}
```

#### Slider
```css
.slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 6px;
  background: var(--bg-overlay);
  border-radius: var(--radius-full);
  outline: none;
  cursor: pointer;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 18px;
  height: 18px;
  background: var(--accent);
  border-radius: 50%;
  cursor: pointer;
  box-shadow: 0 0 10px rgba(6, 182, 212, 0.4);
  transition: all 0.15s ease;
}

.slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
  box-shadow: 0 0 15px rgba(6, 182, 212, 0.6);
}
```

#### Toggle Switch
```css
.toggle {
  position: relative;
  width: 48px;
  height: 26px;
  background: var(--bg-overlay);
  border-radius: var(--radius-full);
  border: 1px solid var(--border-default);
  cursor: pointer;
  transition: all 0.2s ease;
}

.toggle::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  background: var(--text-secondary);
  border-radius: 50%;
  transition: all 0.2s ease;
}

.toggle.active {
  background: var(--accent);
  border-color: var(--accent);
}

.toggle.active::after {
  left: 25px;
  background: #ffffff;
}
```

### 5.3 Cards de Servidor

```python
# SPECIFICAÇÃO DO CARD DE SERVIDOR v2.0

class ServerCard:
    """
    ┌─────────────────────────────────────────────────────────┐
    │ [STATUS]  NOME DO SERVIDOR              [⋮ MENU]      │
    │           IP:Port  •  Mapa                            │
    ├─────────────────────────────────────────────────────────┤
    │  ┌─────────┐  ┌─────────┐  ┌─────────┐               │
    │  │  🟢 UP  │  │  📦 12  │  │  ⏱ 2.4d │               │
    │  │ Players │  │  Mods   │  │ Uptime  │               │
    │  └─────────┘  └─────────┘  └─────────┘               │
    ├─────────────────────────────────────────────────────────┤
    │  [▶ START]  [⏹ STOP]  [🔄 RESTART]  [⚙ CONFIG]      │
    └─────────────────────────────────────────────────────────┘
    """
    
    # Dimensões
    WIDTH = 340
    HEIGHT = 220
    PADDING = 20
    GAP = 12
    
    # Cores do Status (com glow)
    STATUS_COLORS = {
        "running": "#22c55e",
        "stopped": "#6b7280",
        "starting": "#fbbf24",
        "stopping": "#fbbf24",
        "crashed": "#ef4444",
        "updating": "#f59e0b",
    }
    
    # Animação de Status
    STATUS_ANIMATION = {
        "running": "pulse",      # Glow pulsante sutil
        "starting": "spin",       # Ícone girando
        "updating": "progress",   # Barra de progresso
    }
```

### 5.4 Status Badge

```css
/* Badge Padrão */
.badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
  border-radius: var(--radius-full);
}

/* Badge Success */
.badge-success {
  background: var(--badge-success-bg);
  color: var(--badge-success-text);
  border: 1px solid rgba(34, 197, 94, 0.3);
}

/* Badge Warning */
.badge-warning {
  background: var(--badge-warning-bg);
  color: var(--badge-warning-text);
  border: 1px solid rgba(245, 158, 11, 0.3);
}

/* Badge Error */
.badge-error {
  background: var(--badge-error-bg);
  color: var(--badge-error-text);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

/* Badge com LED indicator */
.badge-led::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse 2s infinite;
}
```

### 5.5 Sidebar Navigation

```css
.sidebar {
  width: 240px;
  height: 100vh;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-default);
  display: flex;
  flex-direction: column;
  padding: var(--space-4);
  position: fixed;
  left: 0;
  top: 0;
  z-index: 100;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  transition: all 0.15s ease;
  cursor: pointer;
  margin-bottom: var(--space-1);
}

.sidebar-item:hover {
  background: var(--bg-overlay);
  color: var(--text-primary);
}

.sidebar-item.active {
  background: var(--accent-muted);
  color: var(--accent);
  font-weight: 600;
}

.sidebar-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  width: 3px;
  height: 24px;
  background: var(--accent);
  border-radius: 0 var(--radius-full) var(--radius-full) 0;
}
```

### 5.6 Modal / Dialog

```css
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  opacity: 0;
  animation: fadeIn 0.2s ease forwards;
}

.modal {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-xl);
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  max-width: 90vw;
  max-height: 90vh;
  overflow: hidden;
  transform: scale(0.95) translateY(10px);
  animation: modalIn 0.25s ease forwards;
}

.modal-header {
  padding: var(--space-6);
  border-bottom: 1px solid var(--border-default);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.modal-body {
  padding: var(--space-6);
  overflow-y: auto;
  max-height: 60vh;
}

.modal-footer {
  padding: var(--space-4) var(--space-6);
  border-top: 1px solid var(--border-default);
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

@keyframes fadeIn {
  to { opacity: 1; }
}

@keyframes modalIn {
  to { 
    transform: scale(1) translateY(0);
  }
}
```

---

## 6. Animações e Micro-interações

### 6.1 Princípios de Animação

| Tipo | Duração | Easing | Uso |
|------|---------|--------|-----|
| Instant | 0ms | - | Feedback de clique |
| Fast | 100-150ms | ease-out | Hover states |
| Normal | 200-300ms | ease-in-out | Transições de estado |
| Slow | 400-500ms | ease-out | Modais, painéis |
| Entrance | 300-500ms | ease-out | Elementos novos |

### 6.2 Transições de Hover

```css
/* Card Hover */
.card {
  transition: transform 0.2s ease, 
              box-shadow 0.2s ease,
              border-color 0.2s ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 24px -8px rgba(0, 0, 0, 0.4);
  border-color: var(--accent);
}

/* Button Press */
.btn-primary:active {
  transform: scale(0.97);
  filter: brightness(0.9);
}

/* Icon Rotation */
.icon-spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Pulse Animation (para status) */
.status-pulse {
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

### 6.3 Loading States

```css
/* Skeleton Loading */
.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-overlay) 25%,
    var(--bg-elevated) 50%,
    var(--bg-overlay) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-md);
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Spinner */
.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--bg-overlay);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* Progress Bar */
.progress-bar {
  height: 4px;
  background: var(--bg-overlay);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: var(--gradient-accent);
  border-radius: var(--radius-full);
  transition: width 0.3s ease;
}
```

---

## 7. Guias de Implementação

### 7.1 Estrutura de Arquivos

```
src/
├── ui/
│   ├── __init__.py
│   ├── constants.py          # Paleta de cores, variáveis CSS
│   ├── theme.py               # Gerenciamento de tema (primitive/tek)
│   ├── typography.py          # Configurações de fonte
│   ├── spacing.py             # Sistema de espaçamento
│   ├── components/
│   │   ├── __init__.py
│   │   ├── buttons.py         # CTkButton customizados
│   │   ├── inputs.py          # CTkEntry, CTkSlider, etc.
│   │   ├── cards.py           # Card base, ServerCard
│   │   ├── badges.py          # Status badges
│   │   ├── modals.py          # Dialogs
│   │   ├── sidebar.py         # Navegação
│   │   └── feedback.py        # Toast, Spinner, Skeleton
│   └── animations.py          # Helpers de animação
│
├── styles/
│   ├── theme.css              # CSS variables (se usar webview)
│   └── tokens.json            # Design tokens exportados
│
├── app.py                     # Refatorado com novos componentes
├── ui_constants.py            # Deprecado → migrar para ui/
└── ui_components.py           # Deprecado → migrar para ui/components/
```

### 7.2 Migrando para Novo Sistema

#### 1. Instalar dependências:
```bash
pip install ttkthemes    # Temas avançados para tkinter
pip install Pillow        # Para imagens e ícones
pip install --upgrade customtkinter
```

#### 2. Criar `src/ui/__init__.py`:
```python
"""
ARKLAND UI Design System v2.0
"""
from .constants import (
    COLORS, THEMES, STATUS_COLORS, STATUS_LABELS,
    FONTS, SPACING, BORDER_RADIUS, SHADOWS,
)
from .theme import ThemeManager, get_theme, set_theme
from .components import (
    PrimaryButton, SecondaryButton, DangerButton,
    InputField, SliderField, ToggleSwitch,
    ServerCard, StatusBadge,
    Sidebar, Modal,
    Toast, Spinner, Skeleton,
)
from .animations import fade_in, fade_out, pulse, slide_in

__all__ = [
    # Constants
    "COLORS", "THEMES", "STATUS_COLORS", "STATUS_LABELS",
    "FONTS", "SPACING", "BORDER_RADIUS", "SHADOWS",
    # Theme
    "ThemeManager", "get_theme", "set_theme",
    # Components
    "PrimaryButton", "SecondaryButton", "DangerButton",
    "InputField", "SliderField", "ToggleSwitch",
    "ServerCard", "StatusBadge",
    "Sidebar", "Modal",
    "Toast", "Spinner", "Skeleton",
    # Animations
    "fade_in", "fade_out", "pulse", "slide_in",
]
```

#### 3. Exemplo de Uso - Novo Card de Servidor:

```python
from src.ui import (
    ServerCard, StatusBadge, PrimaryButton,
    get_theme, SPACING, BORDER_RADIUS
)

class NewServerCard(ctk.CTkFrame):
    def __init__(self, parent, server, **kwargs):
        super().__init__(parent, **kwargs)
        
        theme = get_theme()
        
        # Container
        self.configure(
            fg_color=theme["card_bg"],
            corner_radius=BORDER_RADIUS["lg"],
            border_width=1,
            border_color=theme["card_border"],
        )
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=SPACING["4"], pady=SPACING["4"])
        
        # Status indicator
        status_dot = ctk.CTkCanvas(
            header, width=12, height=12,
            bg=theme["card_bg"], highlightthickness=0
        )
        status_dot.create_oval(2, 2, 10, 10, 
                               fill=STATUS_COLORS[server.status],
                               outline="")
        status_dot.pack(side="left", padx=(0, SPACING["3"]))
        
        # Server name
        name_lbl = ctk.CTkLabel(
            header, text=server.name,
            font=FONTS["heading"],
            text_color=theme["text_primary"]
        )
        name_lbl.pack(side="left")
        
        # Badge de status
        badge = StatusBadge(
            header,
            status=server.status,
            text=STATUS_LABELS[server.status]
        )
        badge.pack(side="right")
        
        # Stats row
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.pack(fill="x", padx=SPACING["4"], pady=SPACING["3"])
        stats.grid_columnconfigure((0,1,2), weight=1)
        
        # Player count
        self._stat_card(stats, "Players", str(server.players), 0)
        self._stat_card(stats, "Mods", str(len(server.mods)), 1)
        self._stat_card(stats, "Uptime", server.uptime, 2)
        
        # Action buttons
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=SPACING["4"], pady=SPACING["4"])
        
        PrimaryButton(
            actions, text="▶ Start",
            command=lambda: self._start_server(server)
        ).pack(side="left", padx=(0, SPACING["2"]))
        
        SecondaryButton(
            actions, text="⏹ Stop",
            command=lambda: self._stop_server(server)
        ).pack(side="left")
```

### 7.3 Checklist de Migração

```
□ 1. BACKUP
   □ Criar branch feature/redesign-ui
   □ Commit inicial com código atual

□ 2. DESIGN TOKENS
   □ Criar src/ui/constants.py com todas as cores
   □ Criar src/ui/theme.py com ThemeManager
   □ Criar src/ui/typography.py
   □ Criar src/ui/spacing.py

□ 3. COMPONENTES BASE
   □ PrimaryButton, SecondaryButton, DangerButton
   □ InputField, TextArea
   □ SliderField, ToggleSwitch
   □ CheckboxField, RadioField
   □ DropdownField

□ 4. COMPONENTES COMPOSTOS
   □ Card base
   □ ServerCard (redesign completo)
   □ StatusBadge
   □ StatCard
   □ ActionBar

□ 5. LAYOUT COMPONENTS
   □ Sidebar (novo design)
   □ Header
   □ Modal (novo design)
   □ Toast notifications

□ 6. REFATORAÇÃO DO APP
   □ Migrar app.py para usar novos componentes
   □ Migrar todos os dialogs
   □ Migrar todas as páginas
   □ Atualizar ui_constants.py (deprecar)

□ 7. TESTES
   □ Verificar todos os temas (primitive/tek)
   □ Testar responsividade
   □ Testar animações
   □ Testar acessibilidade (cores, contraste)

□ 8. OTIMIZAÇÃO
   □ Lazy loading de componentes
   □ Cache de widgets
   □ Debounce em inputs
   □ Virtualização de listas longas

□ 9. DOCUMENTAÇÃO
   □ Atualizar README com screenshots
   □ Criar guia de contribuição para UI
   □ Documentar componentes com Storybook-like
```

---

## 8. Roadmap de Implementação

### Fase 1: Foundation (Semana 1)
- [ ] Criar estrutura de arquivos `src/ui/`
- [ ] Implementar `constants.py` com todas as cores
- [ ] Implementar `theme.py` com ThemeManager
- [ ] Testar alternância de temas

### Fase 2: Componentes Core (Semana 2)
- [ ] Buttons (Primary, Secondary, Danger, Icon)
- [ ] Inputs (Text, Number, Slider, Toggle)
- [ ] Cards (Base, ServerCard redesign)
- [ ] Badges (Status, Info, Warning)

### Fase 3: Layout & Navigation (Semana 3)
- [ ] Sidebar com novo design
- [ ] Header component
- [ ] Modal/Dialog component
- [ ] Toast notifications

### Fase 4: Integração (Semana 4)
- [ ] Refatorar `app.py` para novos componentes
- [ ] Migrar todos os dialogs
- [ ] Migrar todas as páginas
- [ ] Depreciar `ui_constants.py` antigo

### Fase 5: Polish & Optimization (Semana 5)
- [ ] Adicionar micro-animações
- [ ] Otimizar performance
- [ ] Testes finais
- [ ] Documentação

---

## 9. Métricas de Sucesso

| Métrica | Atual | Meta | Método |
|---------|-------|------|--------|
| First Contentful Paint | ~1.2s | <0.8s | Performance Profiler |
| Tempo de resposta clique | ~100ms | <50ms | Event tracing |
| Lighthouse Score (UI) | ~65 | >90 | Chrome DevTools |
| Contraste WCAG AA | 3.2:1 | >4.5:1 | Color contrast checker |
| Tamanho bundle Python | ~45MB | <50MB | PyInstaller output |

---

## 10. Conclusão

Este Design System representa uma evolução significativa na interface do ARKLAND Server Manager. O objetivo é criar uma experiência que seja simultaneamente:

1. **Funcional** — Cada elemento serve a um propósito claro
2. **Bela** — Estética profissional alinhada ao universo do jogo
3. **Rápida** — Interações instantâneas e responsivas
4. **Consistente** — Sistema unificado de design tokens

A implementação deve ser gradual, com cada fase entregue e testada antes de prosseguir.

---

*ARKLAND Design System v2.0 — Built with precision, designed with purpose.*
