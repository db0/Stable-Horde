import horde.apis.v2.base as base
import horde.apis.v2.stable as stable
import horde.apis.v2.kobold as kobold
from horde.apis.v2.base import api

api.add_resource(stable.ImageAsyncGenerate, "/generate/async")
api.add_resource(stable.ImageAsyncStatus, "/generate/status/<string:id>")
api.add_resource(stable.ImageAsyncCheck, "/generate/check/<string:id>")
api.add_resource(stable.Aesthetics, "/generate/rate/<string:id>")
api.add_resource(stable.ImageJobPop, "/generate/pop")
api.add_resource(stable.ImageJobSubmit, "/generate/submit")
api.add_resource(kobold.TextAsyncGenerate, "/generate/text/async")
api.add_resource(kobold.TextAsyncStatus, "/generate/text/status/<string:id>")
api.add_resource(kobold.TextJobPop, "/generate/text/pop")
api.add_resource(kobold.TextJobSubmit, "/generate/text/submit")
api.add_resource(base.Users, "/users")
api.add_resource(base.UserSingle, "/users/<string:user_id>")
api.add_resource(base.FindUser, "/find_user")
api.add_resource(base.Workers, "/workers")
api.add_resource(base.WorkerSingle, "/workers/<string:worker_id>")
api.add_resource(base.TransferKudos, "/kudos/transfer")
api.add_resource(base.AwardKudos, "/kudos/award")
api.add_resource(base.HordeModes, "/status/modes")
api.add_resource(stable.HordeLoad, "/status/performance")
api.add_resource(base.Models, "/status/models")
api.add_resource(base.HordeNews, "/status/news")
api.add_resource(base.Heartbeat, "/status/heartbeat")
api.add_resource(base.Teams, "/teams")
api.add_resource(base.TeamSingle, "/teams/<string:team_id>")
api.add_resource(base.OperationsIP, "/operations/ipaddr")
api.add_resource(stable.Interrogate, "/interrogate/async")
api.add_resource(stable.InterrogationStatus, "/interrogate/status/<string:id>")
api.add_resource(stable.InterrogatePop, "/interrogate/pop")
#TODO APIv2 Merge with status as a POST this part of /interrogate/<string:id>
api.add_resource(stable.InterrogateSubmit, "/interrogate/submit")
api.add_resource(base.Filters, "/filters")
api.add_resource(base.FilterRegex, "/filters/regex")
api.add_resource(base.FilterSingle, "/filters/<string:filter_id>")
api.add_resource(stable.ImageHordeStatsTotals, "/stats/img/totals")
api.add_resource(stable.ImageHordeStatsModels, "/stats/img/models")
api.add_resource(kobold.TextHordeStatsTotals, "/stats/text/totals")
api.add_resource(kobold.TextHordeStatsModels, "/stats/text/models")
