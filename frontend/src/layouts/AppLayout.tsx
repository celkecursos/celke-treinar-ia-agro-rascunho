import { Estrutura } from '@celke/kole-react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router';

// Os usos da IA no projeto: prever com um modelo treinado (Previsão), responder (Chat), descobrir (Descobertas)
// e avisar (Alertas).
const NAV = [
  {
    itens: [{ rotulo: 'Análises', icone: 'chart-line', rota: '/' }],
  },
  {
    rotulo: 'Inteligência',
    itens: [
      { rotulo: 'Previsão (treino)', icone: 'brain', rota: '/previsao' },
      { rotulo: 'Chat', icone: 'message-square', rota: '/chat' },
      { rotulo: 'Descobertas', icone: 'lightbulb', rota: '/descobertas' },
      { rotulo: 'Alertas', icone: 'bell', rota: '/alertas' },
    ],
  },
  {
    rotulo: 'Dados',
    itens: [
      { rotulo: 'Municípios', icone: 'map-pin', rota: '/municipios' },
      { rotulo: 'Status e coletas', icone: 'activity', rota: '/status' },
    ],
  },
];

export function AppLayout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();

  return (
    <Estrutura
      marca={{ nome: 'Celke Agro', subtitulo: 'Treinar IA', logo: '/logo.svg', href: '/' }}
      nav={NAV}
      rotaAtual={pathname}
      aoNavegar={(rota) => navigate(rota)}
      renderLink={(p) => (
        <Link to={p.href} className={p.className} onClick={p.onClick} aria-current={p['aria-current']}>
          {p.children}
        </Link>
      )}
      busca={false}
      versao="1.0.0"
      rodape={<span>Dados: Open-Meteo (CC BY 4.0) e IBGE · a IA roda no seu computador com o Ollama</span>}
    >
      <Outlet />
    </Estrutura>
  );
}
