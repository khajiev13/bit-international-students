from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.agent import ProfessorAgentService
from app.api import create_router
from app.config import get_settings
from app.corpus import ProfessorCorpus
from app.question_answer_log import QuestionAnswerLog


def create_app() -> FastAPI:
    settings = get_settings()
    corpus = ProfessorCorpus(settings.corpus_dir)
    question_answer_log = QuestionAnswerLog(settings.qa_log_db_path)
    agent_service = ProfessorAgentService(
        settings=settings,
        corpus=corpus,
        question_answer_log=question_answer_log,
    )

    app = FastAPI(title=settings.app_name)
    app.state.settings = settings
    app.state.corpus = corpus
    app.state.question_answer_log = question_answer_log
    app.state.agent_service = agent_service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.resolved_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.resolved_allowed_hosts)
    app.include_router(create_router())
    return app


app = create_app()
