import { createBrowserRouter } from 'react-router';
import { AppLayout } from './layouts/AppLayout';
import { AlertsPage } from './pages/AlertsPage';
import { AnalysesPage } from './pages/AnalysesPage';
import { ChatPage } from './pages/ChatPage';
import { DiscoveriesPage } from './pages/DiscoveriesPage';
import { ForecastPage } from './pages/ForecastPage';
import { ModelPage } from './pages/ModelPage';
import { MunicipalitiesPage } from './pages/MunicipalitiesPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { StatusPage } from './pages/StatusPage';

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <AnalysesPage /> },
      { path: '/previsao', element: <ForecastPage /> },
      { path: '/descobertas', element: <DiscoveriesPage /> },
      { path: '/alertas', element: <AlertsPage /> },
      { path: '/chat', element: <ChatPage /> },
      { path: '/municipios', element: <MunicipalitiesPage /> },
      { path: '/status', element: <StatusPage /> },
      { path: '/modelo-ia', element: <ModelPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
