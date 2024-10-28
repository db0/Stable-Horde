# SPDX-FileCopyrightText: 2022 Konstantinos Thoukydidis <mail@dbzer0.com>
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import horde.apis.v2.base as base
import horde.apis.v2.kobold as kobold
import horde.apis.v2.stable as stable
from horde.apis.v2.base import api

api.add_resource(stable.ImageAsyncGenerate, "/generate/async")
api.add_resource(stable.ImageAsyncStatus, "/generate/status/<string:id>")
api.add_resource(stable.ImageAsyncCheck, "/generate/check/<string:id>")
api.add_resource(stable.Aesthetics, "/generate/rate/<string:id>")
api.add_resource(stable.ImageJobPop, "/generate/pop")
api.add_resource(stable.ImageJobSubmit, "/generate/submit")
api.add_resource(stable.ImageStyle, "/styles/image")
api.add_resource(stable.SingleImageStyle, "/styles/image/<string:style_id>")
api.add_resource(stable.SingleImageStyleByName, "/styles/image_by_name/<string:style_name>")
api.add_resource(kobold.TextAsyncGenerate, "/generate/text/async")
api.add_resource(kobold.TextAsyncStatus, "/generate/text/status/<string:id>")
api.add_resource(kobold.TextJobPop, "/generate/text/pop")
api.add_resource(kobold.TextJobSubmit, "/generate/text/submit")
api.add_resource(kobold.TextStyle, "/styles/text")
api.add_resource(kobold.SingleTextStyle, "/styles/text/<string:style_id>")
api.add_resource(kobold.SingleImageStyleByName, "/styles/text_by_name/<string:style_name>")
api.add_resource(base.Users, "/users")
api.add_resource(base.UserSingle, "/users/<string:user_id>")
api.add_resource(base.FindUser, "/find_user")
api.add_resource(base.SharedKey, "/sharedkeys")
api.add_resource(base.SharedKeySingle, "/sharedkeys/<string:sharedkey_id>")
api.add_resource(base.Workers, "/workers")
api.add_resource(base.WorkerSingle, "/workers/<string:worker_id>")
api.add_resource(base.WorkerSingleName, "/workers/name/<string:worker_name>")
api.add_resource(base.TransferKudos, "/kudos/transfer")
api.add_resource(base.AwardKudos, "/kudos/award")
api.add_resource(base.HordeModes, "/status/modes")
api.add_resource(base.HordeLoad, "/status/performance")
api.add_resource(base.Models, "/status/models")
api.add_resource(base.ModelSingle, "/status/models/<string:model_name>")
api.add_resource(base.HordeNews, "/status/news")
api.add_resource(base.Heartbeat, "/status/heartbeat")
api.add_resource(base.Teams, "/teams")
api.add_resource(base.TeamSingle, "/teams/<string:team_id>")
api.add_resource(base.OperationsIP, "/operations/ipaddr")
api.add_resource(base.OperationsIPSingle, "/operations/ipaddr/<string:ipaddr>")
api.add_resource(base.OperationsBlockWorkerIP, "/operations/block_worker_ipaddr/<string:worker_id>")
api.add_resource(stable.Interrogate, "/interrogate/async")
api.add_resource(stable.InterrogationStatus, "/interrogate/status/<string:id>")
api.add_resource(stable.InterrogatePop, "/interrogate/pop")
# TODO APIv2 Merge with status as a POST this part of /interrogate/<string:id>
api.add_resource(stable.InterrogateSubmit, "/interrogate/submit")
api.add_resource(base.Filters, "/filters")
api.add_resource(base.FilterRegex, "/filters/regex")
api.add_resource(base.FilterSingle, "/filters/<string:filter_id>")
api.add_resource(stable.ImageHordeStatsTotals, "/stats/img/totals")
api.add_resource(stable.ImageHordeStatsModels, "/stats/img/models")
api.add_resource(kobold.TextHordeStatsTotals, "/stats/text/totals")
api.add_resource(kobold.TextHordeStatsModels, "/stats/text/models")
api.add_resource(base.DocsTerms, "/documents/terms")
api.add_resource(base.DocsPrivacy, "/documents/privacy")
api.add_resource(base.DocsSponsors, "/documents/sponsors")
