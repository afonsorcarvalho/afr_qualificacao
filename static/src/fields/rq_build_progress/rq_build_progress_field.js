/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, onMounted, onWillUnmount, onWillUpdateProps, useState } from "@odoo/owl";

const ACTIVE = ["queued", "running"];
const POLL_MS = 2000;

const DONE_MSG = {
    minuta: "Minuta pronta. Use o botão Minuta para baixar.",
    emissao: "Emissão concluída.",
};

// Banner de montagem: o job roda no cron, fora da requisição do clique; sem
// polling o form só refletiria o progresso com F5.
export class RqBuildProgressField extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ progress: this.props.value || 0 });
        this.timer = null;
        this.stopped = false;
        onWillUpdateProps((next) => {
            this.state.progress = next.value || 0;
        });
        onMounted(() => this.schedule());
        onWillUnmount(() => {
            this.stopped = true;
            clearTimeout(this.timer);
        });
    }

    schedule() {
        if (!this.stopped) {
            this.timer = setTimeout(() => this.poll(), POLL_MS);
        }
    }

    async poll() {
        const record = this.props.record;
        if (!record.resId) {
            return;
        }
        let row;
        try {
            [row] = await this.orm.read(record.resModel, [record.resId],
                ["rq_build_state", "rq_build_progress", "rq_build_kind"]);
        } catch {
            return this.schedule();
        }
        if (this.stopped || !row) {
            return;
        }
        if (ACTIVE.includes(row.rq_build_state)) {
            this.state.progress = row.rq_build_progress || 0;
            return this.schedule();
        }
        this.stopped = true;
        if (row.rq_build_state === "done") {
            this.notification.add(DONE_MSG[row.rq_build_kind] || "Montagem concluída.",
                { type: "success" });
        } else if (row.rq_build_state === "failed") {
            this.notification.add("A montagem do PDF falhou. Veja o aviso no topo do relatório.",
                { type: "danger" });
        }
        const root = record.model.root;
        if (root.isDirty) {
            this.notification.add("Salve o relatório para ver o resultado da montagem.",
                { type: "warning", sticky: true });
            return;
        }
        await root.load();
        record.model.notify();
    }
}

RqBuildProgressField.template = "afr_qualificacao.RqBuildProgressField";
RqBuildProgressField.props = { ...standardFieldProps };
RqBuildProgressField.supportedTypes = ["integer"];

registry.category("fields").add("rq_build_progress_live", RqBuildProgressField);
