import os
import time
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
import json

# Ambiente do Heroku (variáveis de ambiente)
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("GITHUB_REPO")  # Formato: "usuario/repo"
OWNER = os.getenv("GITHUB_OWNER")

# Variáveis globais para controle
build_start_time = None
config_file = "bot_config.json"

def load_config():
    if os.path.exists(config_file):
        with open(config_file, "r") as file:
            return json.load(file)
    return {
        "kernel_source": "https://github.com/thz22/android_kernel_motorola_sm6150.git",
        "kernel_branch": "v10",
        "toolchain_url": "https://github.com/XSans0/WeebX-Clang/releases/download/WeebX-Clang-20.0.0git-release/WeebX-Clang-20.0.0git.tar.gz",
        "anykernel_url": "https://github.com/thz22/AnyKernel3-680.git -b master"
    }

def save_config(config):
    with open(config_file, "w") as file:
        json.dump(config, file, indent=4)

# Função para iniciar workflow
def start_workflow(config, context):
    global build_start_time

    url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/kernel_builder.yml/dispatches"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    data = {
        "ref": config["kernel_branch"],
        "inputs": {
            "KERNEL_SOURCE": config["kernel_source"],
            "KERNEL_BRANCH": config["kernel_branch"],
            "TOOLCHAIN_URL": config["toolchain_url"],
            "ANYKERNEL": config["anykernel_url"],
        },
    }

    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 204:
        build_start_time = time.time()
        context.bot.send_message(chat_id=context.user_data["chat_id"], text="Build iniciada com sucesso!")
    else:
        context.bot.send_message(chat_id=context.user_data["chat_id"], text=f"Erro ao iniciar build: {response.json()}.")

# Função para checar status do workflow
def check_workflow_status(context):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/runs"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        runs = response.json().get("workflow_runs", [])
        if runs:
            latest_run = runs[0]
            status = latest_run.get("status")
            conclusion = latest_run.get("conclusion")
            created_at = latest_run.get("created_at")
            updated_at = latest_run.get("updated_at")

            duration = None
            if build_start_time:
                duration = int(time.time() - build_start_time)

            status_message = f"Última build:\nStatus: {status}\nConclusão: {conclusion}\nIniciada: {created_at}\nFinalizada: {updated_at}"
            if duration:
                status_message += f"\nDuração: {duration // 3600}h {duration % 3600 // 60}m {duration % 60}s"

            context.bot.send_message(chat_id=context.user_data["chat_id"], text=status_message)
        else:
            context.bot.send_message(chat_id=context.user_data["chat_id"], text="Nenhuma build encontrada.")
    else:
        context.bot.send_message(chat_id=context.user_data["chat_id"], text=f"Erro ao verificar status: {response.json()}.")

# Comandos do bot
def start(update: Update, context: CallbackContext):
    context.user_data["chat_id"] = update.effective_chat.id
    config = load_config()

    keyboard = [
        [InlineKeyboardButton("Iniciar Build", callback_data="start_build")],
        [InlineKeyboardButton("Status da Build", callback_data="check_status")],
        [InlineKeyboardButton("Editar Configurações", callback_data="edit_config")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    config_message = (f"Configuração atual:\n"
                      f"Kernel Source: {config['kernel_source']}\n"
                      f"Kernel Branch: {config['kernel_branch']}\n"
                      f"Toolchain URL: {config['toolchain_url']}\n"
                      f"AnyKernel URL: {config['anykernel_url']}\n")

    update.message.reply_text(config_message)
    update.message.reply_text("Escolha uma opção:", reply_markup=reply_markup)

def edit_config(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    config = load_config()

    message = ("Envie as novas configurações no formato:\n"
               "kernel_source=<URL>\n"
               "kernel_branch=<branch>\n"
               "toolchain_url=<URL>\n"
               "anykernel_url=<URL>")
    context.user_data["editing"] = True
    query.edit_message_text(message)

def handle_message(update: Update, context: CallbackContext):
    if context.user_data.get("editing"):
        try:
            config_lines = update.message.text.split("\n")
            config = {}
            for line in config_lines:
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()

            save_config(config)
            context.user_data["editing"] = False
            update.message.reply_text("Configurações atualizadas com sucesso!")
        except Exception as e:
            update.message.reply_text(f"Erro ao atualizar configurações: {e}")

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if query.data == "start_build":
        config = load_config()
        start_workflow(config, context)

    elif query.data == "check_status":
        check_workflow_status(context)

    elif query.data == "edit_config":
        edit_config(update, context)

# Configuração do bot
def main():
    # Inicia o Updater com o TOKEN do bot (definido como variável de ambiente)
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Adiciona handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(CommandHandler("edit_config", edit_config))
    dispatcher.add_handler(CommandHandler("handle_message", handle_message))
    dispatcher.add_handler(CommandHandler("check_status", check_workflow_status))
    dispatcher.add_handler(CommandHandler("start_build", start_workflow))

    dispatcher.add_handler(CallbackQueryHandler(button))

    # Inicia o bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
