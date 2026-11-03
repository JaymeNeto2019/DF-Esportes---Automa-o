# DF Esportes — RSS → Arte PNG + Legenda → Telegram

Ferramentas: RSS público do DF Esportes, Python/Pillow, GitHub Actions (repositório público), Telegram Bot API. Sem chave de IA, Make ou hospedagem paga.

## Passo a passo

1. Abra o Telegram e fale com `@BotFather` (conta verificada). Envie `/newbot`, escolha um nome e um username terminado em `bot`. Guarde o token, **nunca publique o token**.
2. Abra a conversa com seu bot recém-criado e clique em **Start / Iniciar**, ou envie `/start`.
3. No navegador, abra `https://api.telegram.org/botSEU_TOKEN/getUpdates` substituindo apenas `SEU_TOKEN`. Localize `"chat":{"id":123...}` (se ainda não aparecer, envie outra mensagem ao bot e atualize). Guarde o número `chat.id`. Não publique esse link com o token.
4. Crie um **repositório público** vazio no GitHub, por exemplo `dfesportes-telegram`. Se preferir privado, verifique os limites atuais de GitHub Actions do seu plano.
5. Envie para a raiz do repositório **todos** os arquivos desta pasta, inclusive `.github/workflows/telegram.yml`. O arquivo `.github` pode estar oculto em alguns gerenciadores; habilite visualização de arquivos ocultos.
6. No GitHub: **Settings → Secrets and variables → Actions → New repository secret**. Crie `TELEGRAM_BOT_TOKEN` com seu token; crie `TELEGRAM_CHAT_ID` com o ID numérico.
7. Em **Settings → Actions → General**, em **Workflow permissions**, selecione **Read and write permissions** e salve (se esta opção estiver disponível).
8. Em **Actions → DF Esportes - Telegram → Run workflow**, marque `test_mode = true` e execute. Aguarde o resultado. Ele enviará um post de teste com a notícia mais recente e **não** modificará a lista de já vistas.
9. Execute novamente com `test_mode = false`. Na primeira execução normal, o programa registra notícias atuais sem enviá-las, criando `seen.json`. Daí em diante, o agendamento de 10 em 10 minutos tenta detectar e enviar matérias novas.
10. Opcional: envie a imagem do logotipo oficial para `assets/logo.png` (PNG transparente). Sem ela, é usado o texto DF ESPORTES.

## Detalhes importantes

- Arte 1080 × 1350, com fotografia e título originais, categoria e gradiente roxo/laranja. Legenda usa o primeiro parágrafo editorial (heurística; **revise a informação antes de publicar**). O design inicial é aproximado, não uma reprodução exata do Canva.
- O Telegram recebe uma **foto** e uma **mensagem de texto completa**. O sistema **não publica automaticamente no Instagram**.
- Agendamentos do GitHub Actions não são instantâneos: o cron pode atrasar ou ser desativado por inatividade; no plano gratuito e com repositório público, normalmente é possível executar sem pagar, sujeito a limites/regras de uso do GitHub.
- A foto usa a primeira imagem principal (`figure`) no conteúdo RSS. Em matérias com HTML fora do padrão, pode ser necessário ajuste manual.
- O feed normalmente contém um conjunto limitado das matérias mais recentes; se mais posts aparecerem entre verificações que o feed comporte, alguns podem escapar.
- A rotina salva IDs em `seen.json` no GitHub. Como o commit é feito ao final de todo lote, uma falha em um lote pode gerar repetição de parte das mensagens na próxima execução. Um refinamento futuro pode salvar após cada envio.
- Mantenha o bot privado: conhecendo o username, alguém pode iniciar conversa com ele, mas só o chat ID guardado recebe os alertas.
