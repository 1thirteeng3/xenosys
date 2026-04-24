/**
 * NetworkSettings - Cloudflare Tunnel Configuration
 * 
 * This component provides UI for configuring Cloudflare Zero Trust tunnels.
 * Users must create an account on Cloudflare Zero Trust, create a tunnel,
 * and paste the generated token here.
 * 
 * Documentation:
 * https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
 */

import React, { useState } from 'react';
import { saveCloudflareToken, getCloudflareToken } from '../store';

export const NetworkSettings: React.FC = () => {
  const [token, setToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Load existing token on mount
  React.useEffect(() => {
    getCloudflareToken().then(t => {
      if (t) setToken(t.substring(0, 20) + '...'); // Show partial for security
    });
  }, []);

  const handleSave = async () => {
    if (!token.trim()) {
      setMessage({ type: 'error', text: 'Token não pode estar vazio' });
      return;
    }

    setLoading(true);
    setMessage(null);

    try {
      await saveCloudflareToken(token);
      setMessage({ type: 'success', text: 'Token salvo com sucesso!' });
    } catch (err) {
      setMessage({ type: 'error', text: 'Erro ao salvar token' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4 bg-[#1A1A1A] rounded-lg">
      <h2 className="text-xl font-bold text-[#00FF9D] mb-4">Configurações de Rede</h2>
      
      {/* Cloudflare Token Section */}
      <div className="mb-6">
        <label className="block text-[#00FF9D] mb-2">
          Cloudflare Tunnel Token (Zero Trust)
        </label>
        
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="Cole seu token aqui..."
          className="w-full p-3 bg-[#0A0A0A] border border-[#00FF9D] rounded text-[#00FF9D] font-mono"
        />
        
        <p className="text-sm text-gray-400 mt-2 mb-3">
          Necessário para túneis autenticados em produção.
        </p>
        
        <button
          onClick={handleSave}
          disabled={loading}
          className="px-4 py-2 bg-[#00FF9D] text-[#0A0A0A] font-bold rounded hover:bg-[#00CC7D] disabled:opacity-50"
        >
          {loading ? 'Salvando...' : 'Salvar Token'}
        </button>
        
        {message && (
          <p className={`mt-2 ${message.type === 'success' ? 'text-green-400' : 'text-red-400'}`}>
            {message.text}
          </p>
        )}
      </div>

      {/* Instructions */}
      <div className="border-t border-gray-700 pt-4">
        <h3 className="text-lg font-semibold text-[#00FF9D] mb-2">Como obter o token:</h3>
        
        <ol className="list-decimal list-inside text-gray-300 space-y-2">
          <li>Crie uma conta em <a href="https://dash.teams.cloudflare.com/" target="_blank" rel="noopener noreferrer" className="text-[#00FF9D] underline">Cloudflare Zero Trust</a></li>
          <li>Crie um Tunnel na seção "Access" &gt; "Tunnels"</li>
          <li>Selecione "Create a new tunnel" e siga as instruções</li>
          <li>Na etapa de configuração, selecione "Token" como método de autenticação</li>
          <li>Copie o token gerado e cole acima</li>
        </ol>
      </div>
    </div>
  );
};

export default NetworkSettings;