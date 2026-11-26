"""Textos das seções próprias do TPL-MULTI (fonte única para a migração).

`data/proposal_multi_servico_seed.xml` é `noupdate`: bases que já têm as
seções não recebem texto novo pelo `-u`. A migração 16.0.9.3.2 usa estas
constantes para reescrever só o corpo que ainda é o semeado (ver
`hooks._refresh_proposal_multi_texts`). O XML traz o mesmo HTML para
instalações novas; `test_proposal_multi_template` confere que os dois
continuam iguais.

Base: propostas reais da LabQuali de calibração e de NR-13 (2025/2026),
sem dados de cliente.
"""

SECTION_GRP_NR13_BODY = """<div>
<p>Inspeção de segurança de vasos de pressão conforme a NR-13, a ABNT NBR 15417 (vasos de pressão) e a ABNT NBR ISO 31000 (gestão de riscos), executada por Profissional Habilitado nos termos da Decisão Normativa DN 45 do CONFEA/CREA.</p>
<p><strong>Vasos de pressão (autoclaves)</strong></p>
<ul>
<li>Inspeção Baseada em Risco (IBR) do vaso de pressão, avaliando a integridade estrutural e definindo a condição operacional de utilização, com verificação de:
<ul>
<li>mecanismo das portas deslizantes (guilhotina): sapatas soldadas ou aparafusadas, folgas de deslizamento, linearidade dos movimentos, desgaste das cantoneiras, medidas de projeto, dilatações e empenamentos;</li>
<li>mecanismo das portas com fechamento por volante central: hastes de fechamento, fixação nas esferas, aperto dos parafusos-guia, profundidade dos braços além do flange, lubrificação e concentricidade radial;</li>
<li>polimento sanitário da câmara interna (rugosidade conforme projeto), para prevenir trincas por corrosão sob tensão em aços inoxidáveis austeníticos AISI série 300;</li>
<li>produtos e formas de limpeza da câmara interna (decapagem e passivação), para mitigar o surgimento de pites e a degradação do filme passivo do aço AISI 316L;</li>
</ul>
</li>
<li>Medição de espessura por ultrassom das chapas da câmara interna, nos pontos típicos de desgaste;</li>
<li>Ensaio por líquido penetrante nas regiões da câmara interna sujeitas a descontinuidades (dreno e laterais dobradas) e nas linhas de solda da câmara externa;</li>
<li>Ensaio de condutividade da água, para definir ações de polimento e limpeza das chapas;</li>
<li>Inspeção das válvulas de segurança e dos itens de controle e monitoramento de pressão, quanto à conformidade com a legislação, os requisitos regulatórios e os manuais do fabricante.</li>
</ul>
<p><strong>Geradores de vapor</strong></p>
<ul>
<li>Inspeção Baseada em Risco (IBR), avaliando a integridade estrutural e definindo a condição operacional de utilização, com exame visual das luvas e insertos (resistências, controle de nível e segurança);</li>
<li>Avaliação dos processos de limpeza adequados à qualidade da água de abastecimento, para a geração de vapor dentro das especificações normativas;</li>
<li>Inspeção das válvulas de segurança e dos itens de controle e monitoramento, quanto à conformidade com a legislação, os requisitos regulatórios e os manuais do fabricante.</li>
</ul>
<p><strong>Área de instalação</strong></p>
<ul>
<li>Inspeção das instalações conforme os requisitos da NR-13, com relatório de desvios e recomendações para o plano de mitigação de riscos aos usuários, considerando: entradas e saídas da sala onde os vasos estão instalados; condições para manutenção preventiva e corretiva; alimentação de ar e iluminação; iluminação de emergência; planta baixa com a localização do vaso de pressão.</li>
</ul>
<p><strong>Treinamento do Profissional Capacitado</strong></p>
<ul>
<li>O engenheiro mecânico que executa a IBR, Profissional Habilitado pela NR-13, treina um profissional do estabelecimento como Profissional Capacitado, para aplicar e manter a documentação gerada na inspeção de segurança;</li>
<li>O treinamento cobre os itens normativos da NR-13: procedimentos de partida e parada do vaso de pressão; procedimentos e parâmetros operacionais de rotina; procedimentos para situações de emergência; procedimentos gerais de segurança, saúde e preservação do meio ambiente; uso do Livro de Registros (Livro Preto).</li>
</ul>
<p><strong>Documentação entregue</strong></p>
<ul>
<li>Relatório de IBR e prontuário (data sheet) com PMTA, MTA, pressão de teste hidrostático, classe, categoria e grupo do vaso conforme a NR-13 e análise da válvula de segurança;</li>
<li>Relatório de medição de espessura das chapas da câmara interna (parte inferior, superior, laterais e portas);</li>
<li>Laudo do ensaio por líquido penetrante;</li>
<li>Anotação de Responsabilidade Técnica (ART) junto ao CREA;</li>
<li>Relatório de classificação da área de instalação, com definição do Profissional Capacitado e recomendações para o plano de mitigação de riscos;</li>
<li>Abertura do Livro de Registros (Livro Preto);</li>
<li>Certificado de treinamento do Profissional Capacitado.</li>
</ul>
</div>"""

SECTION_GRP_CALIBRACAO_BODY = """<div>
<p><strong>Calibração:</strong> operação que estabelece, sob condições específicas, em uma primeira etapa, uma relação entre os valores e as incertezas de medição fornecidas por padrões e as indicações correspondentes com as incertezas associadas; em uma segunda etapa, utiliza esta informação para estabelecer uma relação visando a obtenção de um resultado de medição a partir de uma indicação. (NBR 16328:2014)</p>
<ul>
<li>Serão utilizados Padrões de Medição calibrados e rastreados à RBC — Rede Brasileira de Calibração / INMETRO;</li>
<li>Os critérios de aceitação são definidos pelo cliente, de acordo com os seus protocolos de calibração formalizados;</li>
<li>Os certificados emitidos contêm tabelas com a média dos valores coletados, a incerteza de medição expandida com nível de confiança de 95% e o coeficiente de abrangência (K), além dos dados dos padrões utilizados e cópia de seus respectivos certificados de calibração;</li>
<li>Será entregue um Certificado de Calibração para cada instrumento calibrado.</li>
</ul>
</div>"""

SECTION_ACEITE_MULTI_BODY = """<div>
<p>Declaro que li, compreendi e concordo com os termos técnicos e comerciais descritos nesta proposta, referente à prestação de serviços de {{ doc._proposal_service_titles() }}, conforme o escopo apresentado. Autorizo {{ company.name }} a iniciar os serviços mediante agendamento prévio, respeitando as condições estabelecidas neste documento.</p>
<p><strong>Dados do responsável pela aprovação</strong></p>
<p>Nome completo: ________________________________ Cargo/Departamento: ____________________<br/>E-mail: ________________________________ Telefone: ____________________<br/>Número do pedido de compra (se aplicável): ________________________________</p>
<p><strong>Dados do responsável pelo pagamento</strong></p>
<p>Nome: ________________________________ Departamento: ____________________<br/>E-mail: ________________________________ Telefone: ____________________</p>
<p><strong>Observações finais</strong></p>
<p>Este aceite confirma a concordância integral com o conteúdo desta proposta, incluindo escopo técnico, prazos de execução e de entrega da documentação, forma de fornecimento da documentação, condições comerciais e demais observações. A proposta somente será considerada aprovada após o preenchimento e a assinatura deste aceite.</p>
<p>O agendamento dos serviços deve ser feito com antecedência e está sujeito à disponibilidade de agenda. Após a aprovação, {{ company.name }} enviará por e-mail as datas disponíveis para a execução; o cliente deve confirmar a data em até 3 (três) dias úteis, sem o que a data poderá ser oferecida a outros clientes.</p>
</div>"""

# {xmlid: (corpo novo, trecho que identifica o corpo semeado antigo,
#          trecho que só existe no corpo novo)}
PROPOSAL_MULTI_TEXT_REFRESH = {
    "proposal_section_grp_nr13": (
        SECTION_GRP_NR13_BODY,
        "[REVISAR — texto provisório]",
        "Inspeção Baseada em Risco",
    ),
    "proposal_section_grp_calibracao": (
        SECTION_GRP_CALIBRACAO_BODY,
        "Será entregue um Certificado de Calibração para cada",
        "critérios de aceitação",
    ),
    "proposal_section_aceite_multi": (
        SECTION_ACEITE_MULTI_BODY,
        "mediante agendamento prévio.",
        "Dados do responsável pela aprovação",
    ),
}
