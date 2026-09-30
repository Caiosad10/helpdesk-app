from kivymd.app import MDApp

import json
import requests

from kivy.lang import Builder
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDRaisedButton, MDIconButton, MDFloatingActionButton
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import MDSnackbar
from kivy.utils import get_color_from_hex
from kivy.uix.screenmanager import ScreenManager, Screen
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.list import OneLineListItem, MDList
from kivymd.uix.scrollview import MDScrollView
from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivymd.uix.datatables import MDDataTable
from kivymd.uix.toolbar import MDTopAppBar
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.uix.scrollview import ScrollView
from kivymd.uix.card import MDCard

import os
import time

KV = """
Screen:
    BoxLayout:
    orientation:'vertical'
    MDLabel:
        id: empty_label
        text: 'Não há nenhum chamado criado'
        halign: 'center'
        theme_text_color: 'Secondary'
    ScrollView:
        MDList:
            id: chamados_container
        MDFloatingActionButton:
            icon: 'plus'
            pos_hint: {'center_x': 0.9, 'center_y':0.1}
            on_release: app.novo_chamado()
"""


class GerenciadorChamados:
    def __init__(self):
        self.chamados = []

   

    def adicionar_chamado(self, usuario, motivo, descricao):
        chamado = {
            "id": len(self.chamados) + 1,
            "usuario": usuario,
            "motivo": motivo,
            "descricao": descricao,
            "status": "Aberto"
        }
        self.chamados.append(chamado)
        print(f"Chamado {chamado['id']} adicionado com sucesso!")

    def listar_chamados(self):
        return self.chamados

class MyApp(MDApp):
    def build(self, first=False):
        self.theme_cls.primary_palette = "Green"
        self.theme_cls.theme_style = "Dark"

        sm = ScreenManager()
        self.gerenciador = GerenciadorChamados()

        sm.add_widget(HelpDeskApp(self.gerenciador, name='helpdesk'))
        sm.add_widget(AbrirChamado(self.gerenciador, name='chamado'))
        #sm.add_widget(ListaChamados(self.gerenciador, name='lista_chamados'))
        #sm.add_widget(DetalhesChamado(name='detalhes_chamado'))

        return sm
    
class HelpDeskApp(MDScreen):
    def __init__(self, gerenciador, **kwargs):
        super().__init__(**kwargs)
        self.gerenciador = gerenciador
        
        with self.canvas.before:
            Color(0,0,0,1) # preto
            self.rect = Rectangle(size=self.size, pos=self.pos)
            self.bind(size=self._update_rect, pos=self._update_rect)

        
        layout = MDBoxLayout(orientation='vertical')
        toolbar = MDTopAppBar(
            title="HelpDesk",
            elevation=4,
            pos_hint={'top': 1},
            size=(dp(200), dp(50)),
            md_bg_color=get_color_from_hex("#121212"),
            specific_text_color=get_color_from_hex("#1DB954"), #fonte verde
            left_action_items=[["menu", lambda x: self.abrir_menu()]],
            right_action_items=[["account", lambda x: self.abrir_perfil()]]
        )
        layout.add_widget(toolbar)

        self.scroll = ScrollView()
        self.chamados_container = MDBoxLayout(orientation='vertical', spacing=10, padding=10, size_hint_y=None)
        self.chamados_container.bind(minimum_height=self.chamados_container.setter('height'))
        self.scroll.add_widget(self.chamados_container)
        layout.add_widget(self.scroll)

        self.add_widget(layout)
        self.add_widget(
            MDFloatingActionButton(
                icon="plus",
                md_bg_color=get_color_from_hex("#1DB954"),
                pos_hint={"center_x": 0.9, "center_y": 0.1},
                elevation= 6,
                on_release=self.abrir_chamado
            )
        )

        self.atualizar_lista_chamado()

    def atualizar_lista_chamado(self):
        self.chamados_container.clear_widgets()
        chamados= self.gerenciador.listar_chamados()

        self.chamados_container.add_widget(
            MDLabel(
                text="Meus Chamados",
                halign="left",
                theme_text_color="Primary",
                font_style="H6",
                size_hint_y= None,
                height=dp(40)
            )
        )

        self.chamados_container.add_widget(Widget(size_hint_y=None, height=dp(50)))
                
        chamados = self.gerenciador.listar_chamados()

        if not chamados:
            mensagem = MDLabel(
                    text="Não há nenhum chamado criado",
                    halign ="center",
                    valign = "center",
                    theme_text_color = "Secondary",
                    size_hint=(1,1)
                )
            self.chamados_container.add_widget(
                MDBoxLayout(mensagem, size_hint=(1,None), height=dp(400), pos_hint={"center_y": 0.5})
            )
        else:
            for chamado in chamados:
                card = MDCard(
                    size_hint=(1, None), height=dp(80),
                    padding=10,
                    md_bg_color=get_color_from_hex("#1E1E1E")
                )
                box = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(70))

                text_box = MDBoxLayout(orientation='vertical')
                text_box.add_widget(MDLabel(text=f"Motivo: {chamado['motivo']}", theme_text_color="Primary"))
                text_box.add_widget(MDLabel(text=f"Descrição: {chamado['descricao']}", theme_text_color="Secondary"))

                menu_button = MDIconButton(
                    icon="dots-vertical",
                    size_hint=(None, None),
                    size=(dp(25), dp(25)),
                    icon_size=dp(15),
                    theme_text_color="Custom",
                    text_color=get_color_from_hex("#000000"),
                    md_bg_color=get_color_from_hex("#1DB954"),
                )
                menu_button.bind(on_release=lambda x, chamado=chamado: self.abrir_menu_acoes(chamado))

                box.add_widget(text_box)
                box.add_widget(menu_button)
                card.add_widget(box)
                self.chamados_container.add_widget(card)

    def abrir_chamado(self, instance):
        self.manager.current = "chamado"

    def abrir_menu_acoes(self, chamado):
        menu_items= [
            {"viewclass": "OneLineListItem", "text": "Editar chamado", "on_release": lambda: self.editar_chamado(chamado)},
            {"viewclass": "OneLineListItem", "text": "Excluir", "on_release": lambda: self.excluir_chamado(chamado)}
        ]
        self.menu = MDDropdownMenu(
            caller=self,
            items=menu_items, 
            width_mult=4)
        self.menu.open()

    def editar_chamado(self, chamado):
        print(f"Editando chamad {chamado['id']}")
        self.menu.dismiss()

    def excluir_chamado(self, chamado):
        self.gerenciador.chamados.remove(chamado)
        self.atualizar_lista_chamado()
        self.menu.dismiss()

    def _update_rect(self, instance, value):
            self.rect.pos = self.pos
            self.rect.size = self.size

    def abrir_menu(self):
        pass

    def abrir_perfil(self):
        pass

class AbrirChamado(MDScreen):
    #dialog = None
    usuario = 'Rafael'
    def __init__(self, gerenciador_chamados, **kwargs):
        super().__init__(**kwargs)
        self.gerenciador_chamados = gerenciador_chamados

        

        layout_principal = MDBoxLayout(orientation='vertical', spacing='12dp', padding='24dp', md_bg_color=get_color_from_hex("#332525"))
        layout_secundario = MDFloatLayout()

        id_usuario = MDLabel(text=f'Usuario: {self.usuario}', font_style='H6', halign='center', theme_text_color='Secondary', pos_hint={'center_x': 0.5,'top': 0.9})

        #Definir botão de motivo como um atributo da classe
        self.button_chamado = MDRaisedButton(
            text='Escolha o motivo',
            md_bg_color=get_color_from_hex("#1DB954"),
            size_hint=(None, None),
            size = (dp(200), dp(50)),
            pos_hint = {'center_x': 0.5, 'top': 0.8},  
            on_press=self.abrir_meu_motivo)
        
        self.descricao_chamado = MDTextField(
            hint_text='Descreva o problema',
            multiline=True,
            size_hint=(None, None),
            size = (dp(200), dp(50)),
            pos_hint = {'center_x': 0.5, 'top': 0.6},
            )
        
        button_confirmacao = MDRaisedButton(
            text='Confirmar Chamado', 
            md_bg_color=get_color_from_hex("#FFA000"),
            size_hint=(None, None),
            size = (dp(200), dp(50)),
            pos_hint = {'center_x': 0.5, 'top': 0.2},  
            on_press=self.confirmar_chamado
            )

        layout_principal.add_widget(id_usuario)
        layout_secundario.add_widget(self.button_chamado)
        layout_secundario.add_widget(self.descricao_chamado)
        layout_secundario.add_widget(button_confirmacao)

        layout_principal.add_widget(layout_secundario)
        self.add_widget(layout_principal)

        self.menu_items = [
            {
                "viewclass": "OneLineListItem",
                "text": "Problema com a conexão",
                "on_release": lambda x="Problema com a conexão": self.selecionar_motivo(x),
            },
            {
                "viewclass": "OneLineListItem",
                "text": "Problema com o site",
                "on_release": lambda x="Problema com o site": self.selecionar_motivo(x),
            },
            {
                "viewclass": "OneLineListItem",
                "text": "Problema com o aplicativo",
                "on_release": lambda x="Problema com o aplicativo": self.selecionar_motivo(x),
            }
        ]

        self.menu_motivo = MDDropdownMenu(
            caller= self.button_chamado,
            items=self.menu_items,
            width_mult=4,
        )

    def abrir_meu_motivo(self, instance):
        self.menu_motivo.caller = instance
        self.menu_motivo.open()

    def selecionar_motivo(self, motivo):
        print(f"motivo selecionado: {motivo}")
        self.button_chamado.text = motivo
        self.menu_motivo.dismiss()

    def confirmar_chamado(self, instance):
        motivo = self.button_chamado.text  # Obtém o motivo selecionado
        descricao = self.descricao_chamado.text  # Obtém a descrição do chamado

        self.gerenciador_chamados.adicionar_chamado(self.usuario, motivo, descricao)

        self.exibir_snackbar()
        
        tela_principal = self.manager.get_screen("helpdesk")
        tela_principal.atualizar_lista_chamado()

        self.manager.current = "helpdesk"

    def exibir_snackbar(self):
        self.snackbar = MDSnackbar(
            MDLabel(
                text="Chamado aberto com sucesso!",
                theme_text_color="Custom",
                text_color= get_color_from_hex("#FFFFFF"),
                font_size= '14sp',
                shorten=False,
                max_lines=1
            ),
            md_bg_color= get_color_from_hex("#4CAF50"),
            size_hint=(None, None),
            size=(dp(275), dp(50)),
            pos_hint={"right": 0.95, "top": 0.89},
        )
        
        
        self.snackbar.open()

if __name__ == '__main__':
    MyApp().run()


