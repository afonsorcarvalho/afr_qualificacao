# -*- coding: utf-8 -*-
from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.addons.portal.controllers.portal import CustomerPortal


class QualifPortalOptional(CustomerPortal):

    @http.route(
        ["/my/orders/<int:order_id>/optional/<int:line_id>/toggle"],
        type="json", auth="public", website=True, methods=["POST"])
    def portal_optional_toggle(self, order_id, line_id, access_token=None,
                               accepted=False, **kw):
        try:
            order_sudo = self._document_check_access(
                "sale.order", order_id, access_token=access_token)
        except (AccessError, MissingError):
            return {"error": "access"}
        try:
            result = order_sudo._portal_toggle_optional(line_id, accepted)
        except UserError as e:
            return {"error": str(e)}
        return result
