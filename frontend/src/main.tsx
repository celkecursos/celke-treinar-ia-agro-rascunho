import '@celke/kole-react/estilos.css';
import './styles.css';
import { ProvedorUi, registrarIcones } from '@celke/kole-react';
import {
  Activity,
  Bell,
  Bot,
  Brain,
  CalendarClock,
  ChartScatter,
  CloudRain,
  Cpu,
  Database,
  History,
  Lightbulb,
  Plus,
  Sparkles,
  Sprout,
  Trash2,
  Wrench,
} from 'lucide-react';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router';
import { router } from './router';

// Ícones usados pelo nome que não vêm registrados no Kole
registrarIcones({
  activity: Activity,
  bell: Bell,
  bot: Bot,
  brain: Brain,
  'calendar-clock': CalendarClock,
  'chart-scatter': ChartScatter,
  'cloud-rain': CloudRain,
  cpu: Cpu,
  database: Database,
  history: History,
  lightbulb: Lightbulb,
  plus: Plus,
  sparkles: Sparkles,
  sprout: Sprout,
  'trash-2': Trash2,
  wrench: Wrench,
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ProvedorUi>
      <RouterProvider router={router} />
    </ProvedorUi>
  </StrictMode>,
);
