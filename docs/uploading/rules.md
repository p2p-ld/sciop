# Rules

{% for rule in config.extra.instance_config.rules %}
## {{ rule.title }}

{{ rule.description }}
{% endfor %} 