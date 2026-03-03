import time
import customtkinter as ctk

class VumeterMixin:
    """Provee métodos para animar los Vúmetros de la GUI.
    Las barras deben estar creadas con place(rely=0.5, anchor='center')
    para que crezcan desde el centro hacia arriba y abajo.
    """

    def _animate_bars(self):
        app = self.app
        if app.is_running:
            for i in range(app.num_bars):
                # ── Entrada (micrófono) ──
                current    = app.current_amplitudes[i]
                target     = app.target_amplitudes[i]
                lerp_speed = 0.4 if target > current else 0.15
                app.current_amplitudes[i] = current + (target - current) * lerp_speed
                height = max(6, int(4 + app.current_amplitudes[i] * 46))
                app.in_bars[i].configure(height=height)
                    
                # ── Salida Micyn ──
                c_out = app.current_amplitudes_out[i]
                t_out = app.target_amplitudes_out[i]
                l_speed_out = 0.4 if t_out > c_out else 0.15
                app.current_amplitudes_out[i] = c_out + (t_out - c_out) * l_speed_out
                h_out = max(6, int(4 + app.current_amplitudes_out[i] * 46))
                app.out_bars[i].configure(height=h_out)
                
            # Gestionar indicador de Espera
            if getattr(app, "is_waiting_audio", False):
                app.vumeter_out_container.place_forget()
                if int(time.time() * 3) % 2 == 0:
                    app.waiting_label_out.place(relx=0.5, rely=0.5, anchor="center")
                else:
                    app.waiting_label_out.place_forget()
            else:
                app.waiting_label_out.place_forget()
                app.vumeter_out_container.place(relx=0.5, rely=0.5, anchor="center")
                
        else:
            app.waiting_label_out.place_forget()
            app.vumeter_out_container.place(relx=0.5, rely=0.5, anchor="center")
            
            for i in range(app.num_bars):
                # Descenso suave micrófono
                if app.current_amplitudes[i] > 0.01:
                    app.current_amplitudes[i] *= 0.8
                    height = max(6, int(4 + app.current_amplitudes[i] * 46))
                    app.in_bars[i].configure(height=height)
                
                # Descenso suave salida
                if app.current_amplitudes_out[i] > 0.01:
                    app.current_amplitudes_out[i] *= 0.8
                    h_out = max(6, int(4 + app.current_amplitudes_out[i] * 46))
                    app.out_bars[i].configure(height=h_out)
        
        if app.winfo_exists():
            app.after(16, self._animate_bars)
