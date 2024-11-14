package com.redhat.coolstore.service;

import jakarta.ejb.ActivationConfigProperty;
import jakarta.ejb.MessageDriven;
import jakarta.inject.Inject;
import org.eclipse.microprofile.reactive.messaging.Incoming;
import org.eclipse.microprofile.reactive.messaging.Message;

import com.redhat.coolstore.model.Order;
import com.redhat.coolstore.utils.Transformers;

@ApplicationScoped
public class OrderServiceMDB {

	@Inject
	OrderService orderService;

	@Inject
	CatalogService catalogService;

	@Incoming("topic/orders")
	public void onMessage(Message<String> message) {
		System.out.println("\nMessage recd !");
		try {
			String orderStr = message.getPayload();
			System.out.println("Received order: " + orderStr);
			Order order = Transformers.jsonToOrder(orderStr);
			System.out.println("Order object is " + order);
			orderService.save(order);
			order.getItemList().forEach(orderItem -> {
				catalogService.updateInventoryItems(orderItem.getProductId(), orderItem.getQuantity());
			});
		} catch (Exception e) {
			throw new RuntimeException(e);
		}
	}

}