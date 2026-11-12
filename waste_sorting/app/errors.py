import logging

from flask import jsonify

log = logging.getLogger("waste_sorting")


class WasteSortingError(Exception):

    status_code = 500
    code = "internal_error"
    subsystem = "core"

    def __init__(self, message=None, *, details=None):
        super().__init__(message or self.__doc__ or self.code)
        self.message = message or self.code
        self.details = details or {}

    def to_dict(self):
        return {"error": {"code": self.code, "subsystem": self.subsystem,
                          "message": self.message, "details": self.details}}


#  Classifier subsystem
class ClassifierError(WasteSortingError):
    code, subsystem = "classifier_error", "classifier"


class InvalidImageError(ClassifierError):
    code, status_code = "invalid_image", 400


class ModelLoadError(ClassifierError):
    code, status_code = "model_load_failed", 503


class InferenceError(ClassifierError):
    code, status_code = "inference_failed", 500


#  AI coach subsystem
class CoachError(WasteSortingError):
    code, subsystem = "coach_error", "coach"


class CoachUnavailableError(CoachError):
    code, status_code = "coach_unavailable", 502


# Rules subsystem
class RulesError(WasteSortingError):
    code, subsystem = "rules_error", "rules"


class InvalidRuleError(RulesError):
    code, status_code = "invalid_rule", 400


# Database subsystem
class StorageError(WasteSortingError):
    code, subsystem = "storage_error", "database"

class DashboardError(WasteSortingError):
    code, subsystem = "dashboard_error", "dashboard"


class SubsystemErrorHandler:

    subsystem = "core"
    error_class = WasteSortingError

    def handle(self, error):
        level = logging.ERROR if error.status_code >= 500 else logging.WARNING
        log.log(level, "[%s] %s: %s", self.subsystem, error.code, error.message)
        return jsonify(error.to_dict()), error.status_code

    def register(self, app):
        app.register_error_handler(self.error_class, self.handle)


class ClassifierErrorHandler(SubsystemErrorHandler):
    subsystem, error_class = "classifier", ClassifierError


class CoachErrorHandler(SubsystemErrorHandler):
    subsystem, error_class = "coach", CoachError


class RulesErrorHandler(SubsystemErrorHandler):
    subsystem, error_class = "rules", RulesError


class DatabaseErrorHandler(SubsystemErrorHandler):
    subsystem, error_class = "database", StorageError

#Dashboard Subsystem
class DashboardErrorHandler(SubsystemErrorHandler):
    subsystem, error_class = "dashboard", DashboardError


def register_error_handlers(app):
    for handler in (ClassifierErrorHandler(), CoachErrorHandler(), RulesErrorHandler(),
                    DatabaseErrorHandler(), DashboardErrorHandler(), SubsystemErrorHandler()):
        handler.register(app)

    @app.errorhandler(413)
    def too_large(_):
        err = InvalidImageError("Image is too large.")
        return jsonify(err.to_dict()), 413

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": {"code": "not_found", "subsystem": "core",
                                  "message": "Not found", "details": {}}}), 404

    @app.errorhandler(Exception)
    def unexpected(exc):
        log.exception("Unhandled error")
        err = WasteSortingError("Something went wrong.")
        return jsonify(err.to_dict()), 500
