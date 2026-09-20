import { useState } from "react";
import { BarChart, Bar, XAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const API_BASE = "http://localhost:5000";

export default function App() {
  const [termo, setTermo] = useState("");
  const [opcoes, setOpcoes] = useState([]);
  const [materiaEscolha, setMateriaEscolha] = useState(null);
  const [ranking, setRanking] = useState([]);
  const [avisos, setAvisos] = useState([]);
  const [carregandoBusca, setCarregandoBusca] = useState(false);
  const [carregandoRanking, setCarregandoRanking] = useState(false);
  const [erro, setErro] = useState("");

  // Estados para o upload de PDF
  const [arquivoPdf, setArquivoPdf] = useState(null);
  const [statusUpload, setStatusUpload] = useState("");

  async function buscarMaterias(e) {
    e.preventDefault();
    setErro("");
    setRanking([]);
    setMateriaEscolha(null);

    if (!termo.trim()) return;

    setCarregandoBusca(true);
    try {
      const r = await fetch(`${API_BASE}/api/materias?q=${encodeURIComponent(termo)}`);
      const data = await r.json();
      setOpcoes(data.opcoes || []);
    } catch (err) {
      setErro("Não foi possível conectar ao backend. Ele está rodando em localhost:5000?");
    } finally {
      setCarregandoBusca(false);
    }
  }

  async function selecionarMateria(nomeMateria) {
    setMateriaEscolha(nomeMateria);
    setCarregandoRanking(true);
    setRanking([]);
    setAvisos([]);
    setErro("");

    try {
      const r = await fetch(`${API_BASE}/api/ranking?materia=${encodeURIComponent(nomeMateria)}`);
      const data = await r.json();
      setRanking(data.ranking || []);
      setAvisos(data.avisos || []);
    } catch (err) {
      setErro("Erro ao buscar o ranking de professores.");
    } finally {
      setCarregandoRanking(false);
    }
  }

  async function fazerUpload(e) {
    e.preventDefault();
    if (!arquivoPdf) return;

    setStatusUpload("Enviando e processando o PDF...");

    const formData = new FormData();
    formData.append("file", arquivoPdf);

    try {
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (res.ok) {
        setStatusUpload("✅ " + data.mensagem);
        setArquivoPdf(null);
        setOpcoes([]);
        setRanking([]);
        setMateriaEscolha(null);
      } else {
        setStatusUpload("❌ Erro: " + data.erro);
      }
    } catch (erro) {
      setStatusUpload("❌ Falha ao conectar com o backend.");
    }
  }

  return (
    <div style={{ maxWidth: "800px", margin: "0 auto", padding: "20px", fontFamily: "sans-serif" }}>
      <h2>Ranking de professores por matéria</h2>
      <p style={{ color: "#666" }}>Baseado nas turmas ofertadas e na distribuição de notas das reviews.</p>

      {/* Seção de Upload do PDF */}
      <div style={{ border: "1px solid #ddd", padding: "15px", marginBottom: "25px", borderRadius: "8px", backgroundColor: "#fdfdfd" }}>
        <h3>Atualizar PDF de Turmas</h3>
        <form onSubmit={fazerUpload} style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <input 
            type="file" 
            accept="application/pdf" 
            onChange={(e) => setArquivoPdf(e.target.files[0])} 
          />
          <button 
            type="submit" 
            disabled={!arquivoPdf}
            style={{ cursor: arquivoPdf ? "pointer" : "not-allowed", padding: "6px 12px" }}
          >
            Substituir PDF
          </button>
        </form>
        {statusUpload && <p style={{ marginTop: "10px", fontSize: "14px", fontWeight: "bold" }}>{statusUpload}</p>}
      </div>

      {/* Caixa de Pesquisa */}
      <form onSubmit={buscarMaterias} style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
        <input
          type="text"
          placeholder="Digite parte do nome da matéria"
          value={termo}
          onChange={(e) => setTermo(e.target.value)}
          style={{ flex: 1, padding: "8px", fontSize: "16px", borderRadius: "4px", border: "1px solid #ccc" }}
        />
        <button type="submit" style={{ padding: "8px 16px", cursor: "pointer" }}>
          {carregandoBusca ? "Buscando..." : "Buscar"}
        </button>
      </form>

      {erro && <p style={{ color: "red" }}>{erro}</p>}

      {/* Lista de Opções de Matérias */}
      {opcoes.length > 0 && (
        <div style={{ marginBottom: "20px" }}>
          <p style={{ fontWeight: "bold" }}>Escolha a matéria:</p>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {opcoes.map((mat) => (
              <button
                key={mat}
                onClick={() => selecionarMateria(mat)}
                style={{
                  padding: "10px",
                  textAlign: "left",
                  cursor: "pointer",
                  backgroundColor: materiaEscolha === mat ? "#e3f2fd" : "#fff",
                  border: "1px solid #ccc",
                  borderRadius: "4px",
                  fontWeight: materiaEscolha === mat ? "bold" : "normal"
                }}
              >
                {mat}
              </button>
            ))}
          </div>
        </div>
      )}

      {carregandoRanking && <p>Carregando ranking e calculando notas...</p>}

      {/* Avisos */}
      {avisos.length > 0 && (
        <div style={{ backgroundColor: "#fffde7", padding: "10px", marginBottom: "15px", border: "1px solid #fff59d", borderRadius: "4px" }}>
          {avisos.map((aviso, idx) => (
            <p key={idx} style={{ fontSize: "13px", color: "#f57f17", margin: "4px 0" }}>⚠️ {aviso}</p>
          ))}
        </div>
      )}

      {/* Exibição do Ranking */}
      {materiaEscolha && !carregandoRanking && (
        <div>
          <h3>Ranking — {materiaEscolha}</h3>
          {ranking.length === 0 ? (
            <p>Nenhum professor encontrado com dados suficientes.</p>
          ) : (
            ranking.map((prof, index) => {
              // Monta os dados para o Recharts com a distribuição A-O
              const dataGrafico = [
                { name: 'A', value: prof.distribuicao?.A || 0, color: '#4caf50' },
                { name: 'B', value: prof.distribuicao?.B || 0, color: '#8bc34a' },
                { name: 'C', value: prof.distribuicao?.C || 0, color: '#ffeb3b' },
                { name: 'D', value: prof.distribuicao?.D || 0, color: '#ff9800' },
                { name: 'F', value: prof.distribuicao?.F || 0, color: '#f44336' },
                { name: 'O', value: prof.distribuicao?.O || 0, color: '#9e9e9e' },
              ];

              return (
                <div key={prof.teacher_id} style={{ border: "1px solid #ddd", padding: "15px", marginBottom: "15px", borderRadius: "8px", backgroundColor: "#fff" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <h4 style={{ margin: "0 0 5px 0" }}>{index + 1}. {prof.professor}</h4>
                      <p style={{ margin: "0 0 10px 0", fontSize: "13px", color: "#666" }}>
                        {prof.papel} · {prof.turma}
                      </p>
                      <a href={prof.url} target="_blank" rel="noreferrer" style={{ fontSize: "14px" }}>
                        Ver reviews ↗
                      </a>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <span style={{ fontSize: "18px", fontWeight: "bold", color: "#2e7d32" }}>
                        {prof.a_percent}% A
                      </span>
                    </div>
                  </div>

                  {/* Gráfico de Distribuição de Conceitos */}
                  <div style={{ height: "100px", width: "100%", marginTop: "15px" }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={dataGrafico} margin={{ top: 5, right: 5, bottom: 5, left: -25 }}>
                        <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                        <Tooltip formatter={(value) => [`${value}%`, 'Porcentagem']} />
                        <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                          {dataGrafico.map((entry, idx) => (
                            <Cell key={`cell-${idx}`} fill={entry.color} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}